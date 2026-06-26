# Copyright 2019 Patrick Wilson <patrickraymondwilson@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from datetime import timedelta

from odoo import fields

from odoo.addons.project.tests.test_project_base import TestProjectCommon


class TestProjectTemplate(TestProjectCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_template = cls.env["project.project"].create(
            {
                "name": "Test Project Template",
                "is_template": True,
            }
        )
        cls.tasks = cls.env["project.task"].create(
            [
                {"name": "Task 1", "project_id": cls.project_template.id},
                {"name": "Task 2", "project_id": cls.project_template.id},
            ]
        )

    def test_create_from_template_preserves_task_date_end(self):
        dates = set()
        now = fields.Datetime.now()
        for index, task in enumerate(self.tasks):
            date_end = now - timedelta(weeks=index)
            task.date_end = date_end
            dates.add(date_end)

        project = self.project_template.action_create_from_template()
        self.assertFalse(project.is_template)
        new_tasks = project.task_ids
        self.assertEqual(len(new_tasks), len(self.tasks))
        self.assertEqual(set(new_tasks.mapped("date_end")), dates)

    def test_regular_copy_clears_task_date_end(self):
        now = fields.Datetime.now()
        for task in self.tasks:
            task.date_end = now

        regular_copy = self.project_template.copy()
        tasks = regular_copy.task_ids
        self.assertEqual(len(tasks), len(self.tasks))
        self.assertFalse(any(tasks.mapped("date_end")))
