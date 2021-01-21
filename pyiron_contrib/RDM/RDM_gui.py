import ipywidgets as widgets
import os
from datetime import datetime

from pyiron_contrib.RDM.internal_widgets import MultiComboBox, MultiTextBox
from pyiron_contrib.RDM.project import Project
from pyiron_contrib.generic.s3io import ProjectS3IO
from pyiron_contrib.RDM.file_browser import FileBrowser
from pyiron_base import InputList

#TODO: Get rid of the hard-coded dictionary!
# Careful - ":" in a key also associated with an header in the S3 put method,
# thus NOT usable as character in any metadata key!
# Introduce metadata class with flatten method taking this into account
TBR_Metadata_Dict = {
    "Filename": ["", None, "str", "hidden"],
    "Owner": ["Me", None, "str", "normal"],
    "Project": ["SFB", None, "str", "fixed"],
    "PI": [["Someone"], None, "strlist", "normal"],
    "Field": [["Theochem", "Physics"], ["Theochem", "Physics", "Arts", "Whatever"], "strlist", "fixed"],
    "Bench": ["Some_Table", ["Some_Table", "Another Table"], "radio", "normal"],
    "PyironID": ["1", None, "str", "fixed"]
}


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
        if project is None:
            project = Project('.')
        self.pr = project.copy()
        self._initial_project = project.copy()
        self.rdm_project = ""
        self.headerbox = widgets.HBox()
        self.bodybox = widgets.VBox()
        self.footerbox = widgets.HBox()

    def list_nodes(self):
        try:
            nodes = [str(val) for val in self.pr.project_info["Resources"].keys()]
        except(AttributeError, ValueError, KeyError):
            nodes = []
        return nodes

    def list_groups(self):
        return self.pr.list_groups()

    def gui(self):
        Hseperator = widgets.HBox(layout=widgets.Layout(border="solid 1px"))
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

    def _update_project_worker(self, rel_path):
        try:
            new_project = self.pr[rel_path]
        except ValueError:
            return "No valid path"
        else:
            if new_project is not None:
                self.pr = new_project

    def change_proj(self, b):
        if b.path == "":
            self.pr = self._initial_project
        else:
            rel_path = os.path.relpath(b.path, self.rdm_project)
            if rel_path == '.':
                return
            self._update_project_worker(rel_path)
        self.rdm_project = b.path
        self._update_body(self.bodybox)
        self._update_header(self.headerbox)

    def open_res(self, b):
        res = GUI_Resource(resource_path=self.rdm_project + b.description,
                           project=self.pr,
                           VBox=self.bodybox,
                           origin=self)
        res.gui()

    def add_resource(self, b):
        add = GUI_AddRecource(project=self.pr, VBox=self.bodybox, origin=self)
        add.gui()

    def add_project(self, b):
        add = GUI_AddProject(project=self.pr, VBox=self.bodybox, origin=self)
        add.gui()

    def _ipython_display_(self):
        try:
            from IPython.display import display
            display(self.gui())
        except ImportError:
            print(repr(self))


class GUI_Resource():
    def __init__(self, resource_path, project=None, VBox=None, origin=None):
        self.path = resource_path
        self.displayed_filesystem = "S3"
        if VBox is None:
            self.bodybox = widgets.VBox()
        else:
            self.bodybox = VBox
        self.pr = project
        if origin is not None:
            self.origin = origin
        self.filebrowser_box = widgets.VBox(layput=widgets.Layout(width="67%",
                                            border="solid 0.5px lightgray"))
        self.metadata_box = widgets.VBox(layout=widgets.Layout(width="33%"))
        self._s3_pr = ProjectS3IO(self.pr, config='config.json', path=self.path)# TODO: replace with actual setup
        self._local_browser = FileBrowser(Vbox=self.filebrowser_box,
                                          project=self.pr)
        self._s3_browser = FileBrowser(Vbox=self.filebrowser_box,
                                       project=self._s3_pr,
                                       fix_path=True,
                                       )
        self.optionbox = widgets.HBox()

    def gui(self):
        self._update_body(self.bodybox)
        self._update_optionbox(self.optionbox)
        self._update_metadatabox(self.metadata_box)
        return self.bodybox

    def _update_metadatabox(self, metabox, metadata_dict=None):
        """
        Update the provided Vbox (intended for the metadata box) using a dictionary of metadata-fields:
        Args:
            metabox: widgets.Vbox whose children will be overwritten
            metadata_dict: dictionary/InputList containing metadata fields
        The dictionary has to have the following structure:
        {Field_Name: [ item(s), option(s), fieldtype, status ]},
            where fieldtype is in ["str","int","strlist","float","date","radiobox"]
            and status is in ["hidden", "fixed", "normal"]
        """
        if metadata_dict is None:
            metabox.children = tuple()
            return
        childs = [widgets.HTML("<h3>File Metadata</h3>")]
        for name, value in metadata_dict.items():
            if value[3] == "fixed":
                disabled = True
            else:
                disabled = False

            if value[2] == "str":
                child = widgets.Text(
                    description=name,
                    value=value[0],
                    disabled=disabled
                )
            elif value[2] == "strlist" and value[1] is None:
                child = MultiTextBox(
                    description=name,
                    value=value[0],
                    options=value[1],
                    disabled=disabled
                ).widget()
            elif value[2] == "strlist":
                child = MultiComboBox(
                    description=name,
                    value=value[0],
                    options=value[1],
                    disabled=disabled
                ).widget()
            elif value[2] == "radio":
                child = widgets.RadioButtons(
                    description=name,
                    options=value[1],
                    value=value[0],
                    disabled=disabled
                )
            else:
                print("Unsupported metadata field type " + str(value[2]))
                child = widgets.HBox()
                child.value = ""
            if value[3] == "hidden":
                child.layout.display = 'none'
            child.old_entry = [name, value]
            childs.append(child)
        metabox.children = tuple(childs)

    def _extract_metadata_dict_from_widget(self):
        metadata_dict = {}
        for widget in self.metadata_box.children[1:]:
            metadata_dict[widget.old_entry[0]] = widget.old_entry[1]
            metadata_dict[widget.old_entry[0]][0] = widget.value
        return metadata_dict

    @staticmethod
    def _flatten_metadata_dict(metadata_dict):
        text_separator = " _and_ "
        flat_metadata = {}
        for key, value in metadata_dict.items():
            if isinstance(value[0], list):
                flat_metadata[key] = text_separator.join([str(elem) for elem in value[0]])
            elif value[0] is None:
                flat_metadata[key] = 'none'
            else:
                flat_metadata[key] = str(value[0])
        return flat_metadata

    def upload_data(self):
        metadata = self._extract_metadata_dict_from_widget()
        metadata = self._flatten_metadata_dict(metadata)
        for data in self._local_browser.data:
            self._s3_pr.put(data, metadata=metadata)

    def _upload_button_clicked(self, b):
        b.disabled = True
        # b.description = "Upload New Data" + " (" + str(b.click_counter) + ")"
        if self.displayed_filesystem == 'local':
            if b.description == "Upload New Data":
                self.upload_data()
            self._s3_browser.update()
        else:
            self.displayed_filesystem = "local"
            self._local_browser.update()
        self._update_optionbox(self.optionbox)
        b.disabled = False

    def _cancel_button_clicked(self, b):
        if b.description == "Cancel":
            self.displayed_filesystem = "S3"
            self._s3_browser.update()
            self._update_optionbox(self.optionbox)
        elif self.origin is not None:
            self.origin.update(bodybox=self.bodybox)

    def _update_optionbox(self, optionbox):
        upload_button = widgets.Button(description="Upload New Data")
        upload_button.on_click(self._upload_button_clicked)

        if self.displayed_filesystem == "local":
            upload_button.tooltip = "Upload Data from local filesystem"
            self._update_metadatabox(self.metadata_box, metadata_dict=TBR_Metadata_Dict)
            cancel_button = widgets.Button(description="Cancel")
        else:
            upload_button.tooltip = "Choose Data from local filesystem to upload"
            self._update_metadatabox(self.metadata_box)
            cancel_button = widgets.Button(description="Close Resource")
        cancel_button.on_click(self._cancel_button_clicked)
        optionbox.children = tuple([upload_button, cancel_button])

    def _update_body(self, bodybox):
        childs = [widgets.HBox([self.filebrowser_box, self.metadata_box]), self.optionbox]
        bodybox.children = tuple(childs)


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
                            if metadata[child.description][1] == 'date' and child.value is not None:
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
                layout=Label.layout
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
                pr = self.pr.open(dic["Project Name:*"][0])
                pr.metadata = dic
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
