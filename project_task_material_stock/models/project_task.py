# Copyright 2015 Tecnativa - Sergio Teruel
# Copyright 2015 Tecnativa - Carlos Dauden
# Copyright 2016-2017 Tecnativa - Vicent Cubells
# Copyright 2019 Valentin Vinagre <valentin.vinagre@qubiq.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
from odoo import _, api, exceptions, fields, models
from odoo.exceptions import UserError


class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    pick_material = fields.Boolean(
        help="If you mark this check, when a task goes to this state, "
             "it will create a stock picking for the associated materials",
    )
    reserve_material = fields.Boolean(
        help="If you mark this check, when a task goes to this state, "
             "it will reserve materials in associated stock.pickings",
    )
    unreserve_material = fields.Boolean(
        help="If you mark this check, when a task goes to this state, "
             "it will unreserve materials in associated stock.pickings",
    )
    done_material = fields.Boolean(
        help="If you mark this check, when a task goes to this state, "
             "it will validate the associated stock.pickings if possible",
    )
    abort_material = fields.Boolean(
        help="If you mark this check, when a task goes to this state, "
             "it will try to unreserve and cancel stock.pickings, if picking is already done, then it will return goods",
    )
    pick_type_id = fields.Many2one(
        comodel_name='stock.picking.type',
        string='Picktype',
        default=lambda self: self.env.ref('project_task_material_stock.project_task_material_picking_type').id
    )
    location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Source Location',
    )
    location_dest_id = fields.Many2one(
        comodel_name='stock.location',
        string='Destination Location',
    )


class StockPicking(models.Model):
    _inherit = "stock.picking"

    task_id = fields.Many2one('project.task', string="Task")


class Task(models.Model):
    _inherit = "project.task"

    @api.multi
    @api.depends('material_ids.stock_move_id')
    def _compute_stock_move(self):
        for task in self:
            task.stock_move_ids = task.mapped('material_ids.stock_move_ids')

    @api.multi
    @api.depends('material_ids.analytic_line_id')
    def _compute_analytic_line(self):
        for task in self:
            task.analytic_line_ids = task.mapped(
                'material_ids.analytic_line_id')

    @api.multi
    @api.depends('stock_move_ids.state')
    def _compute_stock_state(self):
        for task in self:
            if not task.stock_move_ids:
                task.stock_state = 'pending'
            else:
                states = task.mapped("stock_move_ids.state")
                for state in ("confirmed", "assigned", "done"):
                    if state in states:
                        task.stock_state = state
                        break

    @api.multi
    def _compute_matching_picking(self):
        default_pick_type = self.env.ref(
            'project_task_material_stock.project_task_material_picking_type')
        for task in self:
            pick_type = task.pick_type_id or default_pick_type
            pickings = task.picking_ids.filtered(lambda p: p.picking_type_id.id == pick_type.id)
            task.picking_id = pickings[0].id if pickings else None

    picking_ids = fields.One2many(
        "stock.picking",
        "task_id",
        string="Stock Pickings"
    )
    picking_id = fields.Many2one(
        "stock.picking",
        compute="_compute_matching_picking",
        string="Current Picking"
    )
    stock_move_ids = fields.Many2many(
        comodel_name='stock.move',
        compute='_compute_stock_move',
        string='Stock Moves',
    )
    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string='Move Analytic Account',
        help='Move created will be assigned to this analytic account',
    )
    analytic_line_ids = fields.Many2many(
        comodel_name='account.analytic.line',
        compute='_compute_analytic_line',
        string='Analytic Lines',
    )
    pick_material = fields.Boolean(
        related='stage_id.pick_material',
    )
    reserve_material = fields.Boolean(
        related='stage_id.reserve_material',
    )
    unreserve_material = fields.Boolean(
        related='stage_id.unreserve_material',
    )
    done_material = fields.Boolean(
        related='stage_id.done_material',
    )
    abort_material = fields.Boolean(
        related='stage_id.abort_material',
    )
    pick_type_id = fields.Many2one(
        related='stage_id.pick_type_id',
    )
    stage_location_id = fields.Many2one(
        related='stage_id.location_id',
    )
    stage_location_dest_id = fields.Many2one(
        related='stage_id.location_dest_id',
    )
    stock_state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('confirmed', 'Confirmed'),
            ('assigned', 'Assigned'),
            ('done', 'Done')],
        compute='_compute_stock_state',
    )
    location_source_id = fields.Many2one(
        comodel_name='stock.location',
        string='Source Location',
        index=True,
        help='Keep this field empty to use the default value from'
        ' the project.',
    )
    location_dest_id = fields.Many2one(
        comodel_name='stock.location',
        string='Destination Location',
        index=True,
        help='Keep this field empty to use the default value from'
        ' the project.'
    )

    @api.multi
    def unlink_stock_move(self):
        res = False
        moves = self.mapped('stock_move_ids')
        moves_done = moves.filtered(lambda r: r.state == 'done')
        if not moves_done:
            moves.filtered(lambda r: r.state == 'assigned')._do_unreserve()
            moves.filtered(
                lambda r: r.state in {'waiting', 'confirmed', 'assigned'}
            ).write({'state': 'draft'})
            res = moves.unlink()
        return res

    @api.multi
    def _pick_material(self):
        self.ensure_one()
        if not self.picking_id or (self.picking_id and self.picking_id.state == 'draft'):
            todo_lines = self.material_ids.filtered(
                lambda m: not m.stock_move_id
            )
            if todo_lines:
                todo_lines.create_stock_move()
                todo_lines.create_analytic_line()

    @api.multi
    def _reserve_material(self):
        self.ensure_one()
        if not self.picking_id or self.picking_id.state not in ['waiting','confirmed']:
            return
        self.picking_id.action_assign()

    @api.multi
    def _unreserve_material(self):
        self.ensure_one()
        if not self.picking_id or self.picking_id.state not in ['assigned']:
            return
        self.picking_id.do_unreserve()

    @api.multi
    def _abort_material(self):
        self.ensure_one()
        for picking in self.picking_ids:
            if picking.state == 'done':
                # Return the picking
                stock_return_picking = self.env['stock.return.picking'] \
                    .with_context(active_id=picking.id) \
                    .create({})
                stock_return_picking_action = stock_return_picking.create_returns()
                return_pick = self.env['stock.picking'].browse(stock_return_picking_action['res_id'])
                return_pick.action_assign()
                return_pick.move_lines.quantity_done = 1
                return_pick.action_done()
            else:
                picking.action_cancel()

    @api.multi
    def _validate_material(self):
        self.ensure_one()
        if not self.picking_id:
            return
        if self.picking_id.state == 'done':
            return
        res = self.picking_id.button_validate()
        if res and res['res_model'] == 'stock.immediate.transfer':
            # if we get back the immediate transfer wizard - then process it
            wizard = self.env['stock.immediate.transfer'].browse(res['res_id'])
            wizard.process()
        elif res and res['res_model'] == 'stock.overprocessed.transfer':
            raise UserError(_('There are overprocessed stock moves. You have to manually resolv this !'))

    @api.multi
    def write(self, vals):
        res = super(Task, self).write(vals)
        for task in self:
            if 'stage_id' in vals or 'material_ids' in vals:
                if task.done_material:
                    task._pick_material()
                    task.refresh()
                    task._reserve_material()
                    task._validate_material()
                elif task.reserve_material:
                    task._pick_material()
                    task.refresh()
                    task._reserve_material()
                elif task.pick_material:
                    task._pick_material()
                elif task.abort_material:
                    task._abort_material()
                elif task.unreserve_material:
                    task._unreserve_material()
        return res

    @api.multi
    def unlink(self):
        self.mapped('stock_move_ids').unlink()
        self.mapped('analytic_line_ids').unlink()
        return super(Task, self).unlink()

    @api.multi
    def action_assign(self):
        self.mapped('stock_move_ids')._action_assign()

    @api.multi
    def action_done(self):
        for move in self.mapped('stock_move_ids'):
            move.quantity_done = move.product_uom_qty
        self.mapped('stock_move_ids')._action_done()


class StockMove(models.Model):
    _inherit = "stock.move"

    project_task_material_id = fields.Many2one(
        comodel_name='project.task.material',
        string="Task Material"
    )


class ProjectTaskMaterial(models.Model):
    _inherit = "project.task.material"

    @api.multi
    @api.depends('stock_move_ids')
    def _compute_stage_move(self):
        default_pick_type = self.env.ref(
            'project_task_material_stock.project_task_material_picking_type')
        for material in self:
            pick_type = material.task_id.pick_type_id or default_pick_type
            moves = material.stock_move_ids.filtered(
                lambda m: m.picking_type_id.id == pick_type.id)
            material.stock_move_id = moves[0].id if moves else None

    stock_move_id = fields.Many2one(
        comodel_name='stock.move',
        compute='_compute_stage_move',
        string='Stock Move',
    )
    stock_move_ids = fields.One2many(
        comodel_name='stock.move',
        inverse_name='project_task_material_id',
        string='Stock Moves',
    )
    analytic_line_id = fields.Many2one(
        comodel_name='account.analytic.line',
        string='Analytic Line',
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        oldname="product_uom",
        string='Unit of Measure',
    )
    product_id = fields.Many2one(
        domain="[('type', 'in', ('consu', 'product'))]"
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.product_uom_id = self.product_id.uom_id.id
        return {'domain': {'product_uom_id': [
            ('category_id', '=', self.product_id.uom_id.category_id.id)]}}

    def _prepare_stock_move(self):
        product = self.product_id
        res = {
            'product_id': product.id,
            'name': product.partner_ref,
            'state': 'confirmed',
            'project_task_material_id': self.id,
            'product_uom': self.product_uom_id.id or product.uom_id.id,
            'product_uom_qty': self.quantity,
            'origin': self.task_id.name,
            'location_id':
                self.task_id.location_source_id.id or
                self.task_id.stage_id.location_id.id or
                self.task_id.project_id.location_source_id.id or
                self.env.ref('stock.stock_location_stock').id,
            'location_dest_id':
                self.task_id.location_dest_id.id or
                self.task_id.stage_id.location_dest_id.id or
                self.task_id.project_id.location_dest_id.id or
                self.env.ref('stock.stock_location_customers').id,
        }
        return res

    @api.multi
    def create_stock_move(self):
        task = self[0].task_id
        pick_type = task.pick_type_id
        if not pick_type:
            pick_type = self.env.ref(
                'project_task_material_stock.project_task_material_picking_type')
        # Do search for matching picking
        picking_id = task.picking_id or self.env['stock.picking'].create({
            'origin': "{}/{}".format(task.project_id.name, task.name),
            'partner_id': task.partner_id.id,
            'task_id': task.id,
            'picking_type_id': pick_type.id,
            'location_id':
                task.location_source_id.id or
                task.stage_id.location_id.id or
                task.project_id.location_source_id.id or
                self.env.ref('stock.stock_location_stock').id,
            'location_dest_id':
                task.location_dest_id.id or
                task.stage_id.location_dest_id.id or
                task.project_id.location_dest_id.id or
                self.env.ref('stock.stock_location_customers').id,
        })
        for line in self:
            if not line.stock_move_id:
                move_vals = line._prepare_stock_move()
                move_vals.update({'picking_id': picking_id.id or False})
                self.env['stock.move'].create(move_vals)

    def _prepare_analytic_line(self):
        product = self.product_id
        company_id = self.env['res.company']._company_default_get(
            'account.analytic.line')
        analytic_account = getattr(self.task_id, 'analytic_account_id', False)\
            or getattr(self.task_id.project_id, 'analytic_account_id', False)
        if not analytic_account:
            raise exceptions.Warning(
                _("You must assign an analytic account for this task/project.")
            )
        res = {
            'name': self.task_id.name + ': ' + product.name,
            'ref': self.task_id.name,
            'product_id': product.id,
            'unit_amount': self.quantity,
            'account_id': analytic_account.id,
            'user_id': self._uid,
            'product_uom_id': self.product_uom_id.id,
            'company_id': analytic_account.company_id.id or
            self.env.user.company_id.id,
            'partner_id': self.task_id.partner_id.id or
            self.task_id.project_id.partner_id.id or None,
            'task_material_id': [(6, 0, [self.id])],
        }
        amount_unit = \
            self.product_id.with_context(uom=self.product_uom_id.id).price_get(
                'standard_price')[self.product_id.id]
        amount = amount_unit * self.quantity or 0.0
        result = round(amount, company_id.currency_id.decimal_places) * -1
        vals = {'amount': result}
        if 'employee_id' in self.env['account.analytic.line']._fields:
            vals['employee_id'] = \
                self.env['hr.employee'].search([
                    ('user_id', '=', self.task_id.user_id.id)
                ], limit=1).id
        res.update(vals)
        return res

    @api.multi
    def create_analytic_line(self):
        for line in self:
            self.env['account.analytic.line'].create(
                line._prepare_analytic_line())

    @api.multi
    def unlink_stock_move(self):
        if not self.stock_move_id.state == 'done':
            if self.stock_move_id.state == 'assigned':
                self.stock_move_id._do_unreserve()
            if self.stock_move_id.state in (
               'waiting', 'confirmed', 'assigned'):
                self.stock_move_id.write({'state': 'draft'})
            picking_id = self.stock_move_id.picking_id
            self.stock_move_id.unlink()
            if not picking_id.move_line_ids_without_package and \
               picking_id.state == 'draft':
                picking_id.unlink()

    @api.multi
    def _update_unit_amount(self):
        # The analytical amount is updated with the value of the
        # stock movement, because if the product has a tracking by
        # lot / serial number, the cost when creating the
        # analytical line is not correct.
        for sel in self.filtered(lambda x: x.stock_move_id.state == 'done' and
                                 x.analytic_line_id.amount !=
                                 x.stock_move_id.value):
            sel.analytic_line_id.amount = sel.stock_move_id.value

    @api.multi
    def unlink(self):
        self.unlink_stock_move()
        if self.stock_move_id:
            raise exceptions.Warning(
                _("You can't delete a consumed material if already "
                  "have stock movements done.")
            )
        self.analytic_line_id.unlink()
        return super(ProjectTaskMaterial, self).unlink()
