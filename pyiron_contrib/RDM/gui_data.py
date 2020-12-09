from pyiron_contrib.RDM.file_browser import FileBrowser


class GUI_Data:
    def __init__(self, project, msg=None):
        self.project = project
        self.filewidget = FileBrowser()
        self.msg = msg

    def refresh(self):
        pass

    def _get_data(self):
        self.data = self.filewidget.data

    def list_data(self):
        self._get_data()
        return self.data

    def gui(self):
        # print('start gui', self)
        self.filebrws = self.filewidget.gui()
        #       self.data_name = widgets.Text(
        #           value='',
        #           placeholder='Type something',
        #           description='File Name:',
        #           disabled=False
        #       )
        return self.filebrws