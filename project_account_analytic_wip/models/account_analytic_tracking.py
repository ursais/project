# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class AnalyticTrackingItem(models.Model):
    _inherit = "account.analytic.tracking.item"

    project_task_id = fields.Many2one(
        "project.task", string="Project Task", ondelete="restrict"
    )

    def _compute_name(self):
        super()._compute_name()
        for tracking in self.filtered("project_task_id"):
            move = tracking.project_task_id
            # TODO: raw_material_production_id in project_task...
            tracking.name = "{} / {}".format(
                move.raw_material_production_id.display_name,
                move.product_id.display_name,
            )

    @api.depends("manual_planned_amount", "project_task_id")
    def _compute_planned_amount(self):
        super()._compute_planned_amount()
        for tracking in self.filtered("project_task_id"):
            task = tracking.project_task_id
            sale_line_id = task.sale_line_id
            qty = sale_line_id.product_uom_qty
            unit_cost = sale_line_id.product_id.standard_price
            tracking.manual_planned_amount += qty * unit_cost
