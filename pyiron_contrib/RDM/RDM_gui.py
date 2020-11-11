import ipywidgets as widgets
import os
from datetime import datetime

from pyiron_contrib.RDM.internal_widgets import MultiComboBox, MultiTextBox
from pyiron_contrib.RDM.project import Project
from pyiron_contrib.RDM.gui_data import FileBrowser
from pyiron_base import InputList

class GUI_RDM:
    """
    Access to the Research Data Management (RDM) system
    """

    def __init__(self, project=None, Vbox=None):
        if Vbox is None:
            self.box = widgets.VBox()
        else:
            self.box = Vbox
        # rmd_project is a relative path like string representation
        self.default_proj = "SFB1394"
        if project is not None:
            self.default_proj = project.base_name
        self.pr = project
        self.list_groups()
        self.rdm_project = ""

    def list_nodes(self):
        try:
            nodes = [str(val) for val in self.pr.project_info["Resources"].keys()]
        except:
            nodes = []
        return nodes

    def list_groups(self):
        if self.pr is None:
            pr = Project(self.default_proj)
            return pr.parent_group.list_groups()
        else:
            return self.pr.list_groups()

    def gui(self):
        self.headerbox = widgets.HBox()
        Hseperator = widgets.HBox(layout=widgets.Layout(border="solid 1px"))
        self.bodybox = widgets.VBox()
        self.footerbox = widgets.HBox()
        self._update_header(self.headerbox)
        self._update_body(self.bodybox)
        self.box.children = tuple([self.headerbox, Hseperator, self.bodybox, self.footerbox])
        return self.box

    def update(self, headerbox=None, bodybox=None, footerbox=None):
        if headerbox is not None:
            self.headerbox = headerbox
        if bodybox is not None:
            self.bodybox = bodybox
        if footerbox is not None:
            self.footerbox = footerbox
        self._update_header(self.headerbox)
        self._update_body(self.bodybox)

    def _update_body(self, box):
        btnLayout = widgets.Layout(color="green", height="120px", width="120px")
        res_buttons = []
        for res in self.list_nodes():
            button = widgets.Button(description=res, icon="fa-briefcase", layout=btnLayout)
            button.on_click(self.open_res)
            res_buttons.append(button)
        button = widgets.Button(description="Add Resource", icon="fa-plus-circle", layout=btnLayout)
        button.on_click(self.add_resource)
        res_buttons.append(button)
        proj_buttons = []
        for proj in self.list_groups():
            button = widgets.Button(description=proj, icon="fa-folder", layout=btnLayout)
            button.path = self.rdm_project + proj + '/'
            button.on_click(self.change_proj)
            proj_buttons.append(button)
        button = widgets.Button(description="Add Project", icon="fa-plus-circle", layout=btnLayout)
        button.on_click(self.add_project)
        proj_buttons.append(button)
        childs = []
        if len(self.rdm_project.split("/")) > 1:
            childs.append(widgets.HTML("<h2>Resources:</h2>"))
            resBox = widgets.HBox(res_buttons)
            resBox.layout.flex_flow = "row wrap"
            childs.append(resBox)
            childs.append(widgets.HTML("<h2>Sub-Projects:</h2>"))
        else:
            childs.append(widgets.HTML("<h2>Projects:</h2>"))
        projBox = widgets.HBox(proj_buttons)
        projBox.layout.flex_flow = "row wrap"
        childs.append(projBox)
        box.children = tuple(childs)

    def _update_header(self, box):
        buttons = []
        tmppath_old = self.rdm_project + ' '
        tmppath = os.path.split(self.rdm_project)[0]
        while tmppath != tmppath_old:
            tmppath_old = tmppath
            [tmppath, proj] = os.path.split(tmppath)
            button = widgets.Button(description=proj, layout=widgets.Layout(width='auto'))
            button.style.button_color = '#DDDDAA'
            button.path = tmppath_old + '/'
            button.on_click(self.change_proj)
            buttons.append(button)
        button = widgets.Button(icon="fa-home", layout=widgets.Layout(width='auto'))
        button.path = ""
        button.style.button_color = '#999999'
        button.on_click(self.change_proj)
        buttons[-1] = button
        buttons.reverse()
        box.children = tuple(buttons)

    def change_proj(self, b):
        self.rdm_project = b.path
        if b.path == "":
            self.pr = None
        else:
            self.pr = Project(self.rdm_project)
        self.rdm_projects = self.list_groups()
        self._update_body(self.bodybox)
        self._update_header(self.headerbox)

    def open_res(self, b):
        filebrowser = FileBrowser(s3path=self.rdm_project + b.description,
                     fix_s3_path=True,
                     storage_system='S3')
        self.bodybox.children = tuple([filebrowser.widget()])

    def add_resource(self, b):
        add = GUI_AddRecource(project=self.pr, VBox=self.bodybox, origin=self)
        add.gui()

    def add_project(self, b):
        add = GUI_AddProject(project=self.pr, VBox=self.bodybox, origin=self)
        add.gui()


class GUI_AddProject():
    def __init__(self, project=None, VBox=None, origin=None):
        if VBox is None:
            self.bodybox = widgets.VBox()
        else:
            self.bodybox = VBox
        self.pr = project
        self.old_metadata = None
        if hasattr(self.pr, 'metadata'):
            if isinstance(self.pr.metadata, InputList):
                if self.pr.metadata.has_keys():
                    self.old_metadata = self.pr.metadata
        if origin is not None:
            self.origin = origin

    def gui(self):
        self._update(self.bodybox)
        return self.bodybox

    def _update(self, box, _metadata=None):
        def on_click(b):
            if b.description == "Submit":
                for child in childs:
                    if hasattr(child, 'value') and (child.description != ""):
                        try:
                            if metadata[child.description][1] == 'date':
                                value = datetime.toordinal(child.value)
                            else:
                                value = child.value
                            metadata[child.description][0] = value
                        except KeyError:
                            metadata[child.description] = [child.value, 'unknown']
                self.add_proj(metadata)
            if b.description == 'Copy Metadata':
                self._update(box, _metadata=self.old_metadata)
            if b.description == 'Clear Metadata':
                self._update(box)
            if b.description == 'Cancel':
                if self.origin is not None:
                    self.origin.update(bodybox=self.bodybox)

        childs = []
        childs.append(widgets.HTML("<h2>Create Project:</h2>"))
        for field in ["Project Name", "Display Name"]:
            childs.append(widgets.Text(
                value='',
                placeholder=field,
                description=field + ":*",
                disabled=False,
                layout=widgets.Layout(width="80%"),
                style={'description_width': '25%'}
            ))
        childs.append(widgets.Textarea(
            value="",
            placeholder="Project Description",
            description="Project Description:*",
            disable=False,
            layout=widgets.Layout(width="80%"),
            style={'description_width': '25%'}
        ))
        childs.append(widgets.HBox(layout=widgets.Layout(border="solid 0.5px lightgray")))
        childs.append(widgets.HTML("<h3>Project Metadata</h3>"))

        if self.old_metadata is not None:
            Label = widgets.Label(
                value="Copy metadata from ",
                layout=widgets.Layout(
                    width="99%",
                    display="flex",
                    justify_content="center"
                ))
            Label2 = widgets.Label(
                value="'" + self.pr.base_name + "'",
                layout = Label.layout
                #widgets.Layout(
                #    width="30%",
                #    display="flex",
                #    justify_content="center"
            )#)
            Button = widgets.Button(description="Copy Metadata")
            Button.on_click(on_click)
            Button2 = widgets.Button(description="Clear Metadata", height="auto")
            Button2.on_click(on_click)
            childs.append(widgets.HBox(
                [widgets.VBox([Label, Label2],
                              layout=widgets.Layout(width="30%")),
                Button,
                Button2
                 ],
                layout=widgets.Layout(width="85%")
            ))
            #childs.append(widgets.HBox(
            #    [Label],
            #    layout=widgets.Layout(width="85%")
            #))
            #childs.append(widgets.HBox([Label2, Button, Button2], layout=widgets.Layout(width="85%")))

        if _metadata is None:
            metadata = {
                'Principal Investigators (PIs):*': [[], 'stringlist'],
                'Project Start:*': [None, 'date'],
                'Project End:*': [None, 'date'],
                'Discipline:*': [[], 'stringlist'],
                'Participating Organizations:*': [[], 'stringlist'],
                'Project Keywords:': [[], 'stringlist'],
                'Visibility:*': ["Project Members", 'radiobox'],
                'Grand ID:': [None, 'string']
            }
        else:
            metadata = _metadata.to_builtin()

        childs.append(MultiTextBox(
            description="Principal Investigators (PIs):*",
            placeholder="Principal Investigators (PIs)",
            value=metadata["Principal Investigators (PIs):*"][0],
            disable=False,
            layout=widgets.Layout(width="85%"),
            style={'description_width': '30%'}
        ).widget())

        date = metadata["Project Start:*"][0]
        if date is not None:
            date = datetime.fromordinal(date).date()
        childs.append(widgets.DatePicker(
            description="Project Start:*",
            value=date,
            layout=widgets.Layout(width="50%", display="flex"),
            style={'description_width': '50%'}
        ))

        date = metadata["Project End:*"][0]
        if date is not None:
            date = datetime.fromordinal(date).date()
        childs.append(widgets.DatePicker(
            description="Project End:*",
            value=date,
            layout=widgets.Layout(width="50%"),
            style={'description_width': '50%'}
        ))
        childs.append(MultiComboBox(
            description="Discipline:*",
            value=metadata["Discipline:*"][0],
            placeholder="Discipline",
            options=["Theoretical Chemistry", "Arts"],
            layout=widgets.Layout(width="85%"),
            style={'description_width': '30%'}
        ).widget())
        childs.append(MultiComboBox(
            description='Participating Organizations:*',
            value=metadata['Participating Organizations:*'][0],
            placeholder="Participating Organizations:",
            options=["MPIE", "RWTH"],
            layout=widgets.Layout(width="85%"),
            style={'description_width': '30%'}
        ).widget())
        childs.append(MultiTextBox(
            description='Project Keywords:',
            value=metadata['Project Keywords:'][0],
            placeholder="Keywords",
            layout=widgets.Layout(width="85%"),
            style={'description_width': '30%'}
        ).widget())
        childs.append(widgets.RadioButtons(
            description='Visibility:*',
            value=metadata['Visibility:*'][0],
            options=["Project Members", "Public"],
            layout=widgets.Layout(width="50%"),
            style={'description_width': '50%'}
        ))
        childs.append(widgets.Text(
            description='Grand ID:',
            placeholder='Grand ID',
            value=metadata['Grand ID:'][0],
            layout=widgets.Layout(width="85%"),
            style={'description_width': '30%'}
        ))

        SubmitButton = widgets.Button(description="Submit")
        CalcelButton = widgets.Button(description="Cancel")
        SubmitButton.on_click(on_click)
        CalcelButton.on_click(on_click)
        childs.append(widgets.HBox([SubmitButton, CalcelButton]))
        box.children = tuple(childs)

    def add_proj(self, dic):
        if self.pr is not None:
            #try:
                pr = self.pr.open(dic["Project Name:*"][0])
                pr.metadata = dic
            #except None:
            #    print ("Failed to open new project.")
        else:
            #try:
                pr = Project(dic["Project Name:*"])
                pr.metadata = dic
            #except None:
            #    print("Failed to open new project.")
        pr.save_metadata()
        if self.origin is not None:
            self.origin.update(bodybox=self.bodybox)
        else:
            self.bodybox.children = tuple([widgets.HTML("Project added")])


class GUI_AddRecource():
    def __init__(self, project, VBox=None, origin=None):
        if VBox is None:
            self.bodybox = widgets.VBox()
        else:
            self.bodybox = VBox
        self.pr = project
        self.old_metadata = None
        if hasattr(self.pr, 'metadata'):
            if isinstance(self.pr.metadata, InputList):
                if self.pr.metadata.has_keys():
                    self.old_metadata = self.pr.metadata
        if origin is not None:
            self.origin = origin

    def gui(self):
        self._update(self.bodybox)
        return self.bodybox

    def _update(self, box, _metadata=None):
        def on_click(b):
            if b.description == "Submit":
                try:
                    self.pr.project_info["Resources"][Name_Field.value] = metadata
                except KeyError:
                    self.pr.project_info["Resources"] = InputList()
                    self.pr.project_info["Resources"][Name_Field.value] = metadata
                self.pr._save_projectinfo()
                if self.origin is not None:
                    self.origin.update(bodybox=self.bodybox)
                else:
                    self.bodybox.children = tuple([widgets.HTML("Resource added")])
            if b.description == 'Cancel':
                if self.origin is not None:
                    self.origin.update(bodybox=self.bodybox)

        childs = []
        childs.append(widgets.HTML("<h2>Create Resource:</h2>"))

        Name_Field = widgets.Text(
            value='',
            placeholder="Name",
            description= "Name" + ":*",
            disabled=False,
            layout=widgets.Layout(width="80%"),
            style={'description_width': '25%'}
        )
        childs.append(Name_Field)

        if _metadata is None:
            metadata = {}
        else:
            metadata = _metadata.to_builtin()

        SubmitButton = widgets.Button(description="Submit")
        CalcelButton = widgets.Button(description="Cancel")
        SubmitButton.on_click(on_click)
        CalcelButton.on_click(on_click)
        childs.append(widgets.HBox([SubmitButton, CalcelButton]))

        box.children = tuple(childs)
