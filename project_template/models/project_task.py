# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models


class ProjectTask(models.Model):
    _inherit = "project.task"

    def _project_template_preserve_date_end(self):
        return self.env.context.get("copy_from_template")

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        if self._project_template_preserve_date_end():
            for task, vals in zip(self, vals_list, strict=True):
                vals["date_end"] = task.date_end
        return vals_list

    def update_date_end(self, stage_id):
        if self._project_template_preserve_date_end():
            return {}
        return super().update_date_end(stage_id)
