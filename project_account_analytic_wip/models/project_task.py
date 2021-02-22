# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import models


class ProjectTask(models.Model):
    _name = "project.task"
    _inherit = ["project.task", "account.analytic.tracked.mixin"]

    def _prepare_tracking_item_domain(self):
        self.ensure_one()
        return [("project_task_id", "=", self.id)]

    def _prepare_tracking_item_values(self):
        vals = super()._prepare_tracking_item_values()
        analytic = self.raw_material_production_id.analytic_account_id
        if analytic:
            vals.update(
                {
                    "analytic_id": analytic.id,
                    "product_id": self.sale_line_id.product_id.id,
                    "project_task_id": self.id,
                }
            )
        return vals

    def _prepare_mrp_raw_material_analytic_line(self):
        self.ensure_one()
        vals = super()._prepare_mrp_raw_material_analytic_line()
        vals["analytic_tracking_item_id"] = self.analytic_tracking_item_id.id
        return vals
