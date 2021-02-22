# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import models


class ProjectProject(models.Model):
    _inherit = "project.project"

    def write(self, vals):
        res = super().write(vals)
        if "analytic_account_id" in vals:
            self.task_ids.set_tracking_item()
        return res
