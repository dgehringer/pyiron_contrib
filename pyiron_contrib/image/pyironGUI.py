from ipytree import Tree, Node
from pyiron import Project
from ipywidgets import link, HBox, VBox, IntSlider, Text, Label, Button, Output
import ipywidgets as widgets
from IPython.display import display
import matplotlib.pyplot as plt

import os
import numpy as np
import pandas
import html


class ProjectItem(Node):
    def __init__(self, name, pr, name_print=None, loaded=False, **qwargs):
        self.pr = pr
        self.loaded = loaded
        self._pr_name = name
        if name_print is not None:
            name = name_print
        super().__init__(name, **qwargs) 
        

_output = Output()

class ProjectTree:
    def __init__(self, project, debug=False):
        self._project = pyironWrapper(project)
        self._project_home = project.copy()
        self._path = ""
        self._debug = debug

        if debug:
            self.w_text = _output  
            self.w_text.layout.height = '600px'
            self.w_text.layout.width = '600px'
            self.w_text.clear_output()
        else:         
            self.w_text = widgets.Output(
                layout=widgets.Layout(width='600px', height='600px', overflow_y='auto'))
        
        self._tree = Tree(stripes=True, multiple_selection=False)
        self._tree.layout.width = '100%'        
        
        self._home = widgets.Button(description='Home: {}'.format(project.name))
        
        self._back = widgets.Button()
        if project['..'] is None:
            self._back.layout.visibility = 'hidden'
        else:
            self._back.description = 'Back: {}'.format(project['..'].name)
            self._back.layout.visibility = 'visible'
        
        self._home.on_click(self.go_home) 
        self._back.on_click(self.go_back) 

        self._node_name = None
        
    def _clear_tree(self):
        for t_node in self._tree.nodes:
            self._tree.remove_node(t_node)
            
    def _show_tree(self, project):
        self._clear_tree()
        node = ProjectItem(project.name, project)
        self._tree.add_node(node)
        self._open_node(node, project) 
        
    @_output.capture()
    def go_back(self, b):
        pr = self._project
        self._show_tree(pr)
        self._project = pr['..']
        if self._project is None:
            self._back.layout.visibility = 'hidden'
            return
        self._back.layout.visibility = 'visible'
        self._back.description = 'Back: {}'.format(self._project.name)
        
    @_output.capture()
    def go_home(self, b):
        self._project = pyironWrapper(self._project_home)
        self._show_tree(self._project)
        
    def show(self): 
        self._show_tree(self._project)
        return HBox([VBox([
                           HBox([self._home, self._back]), 
                           HBox([self._tree])]), 
                     self.w_text
                    ], layout=widgets.Layout(height='600px'))
    
    @_output.capture()
    def _open_node(self, node, pr): 
        if self._debug:
            print ('_open_node: ', type(node), type(pr))
        node_filter = ['NAME', 'TYPE', 'VERSION']
        file_ext_filter = ['.h5', '.db']
        
        if node.loaded:
            node.opened = True
            return
        
        # https://fontawesome.com/icons
        for g in pr.list_groups():
            node_g = ProjectItem(g, pr, icon='angle-right', icon_style='success')
            node_g.observe(self._handle_click, 'selected')
#             node_g.icon_style = 'warning'
            node.add_node(node_g)
 
        if isinstance(pr._wrapped_obj, listFiles):
            for g in pr.list_nodes():
                _, file_extension = os.path.splitext(g)
                if file_extension not in file_ext_filter:
                    node_g = ProjectItem(g, pr._obj, icon='file')
                    node_g.observe(self._handle_click, 'selected')
                    node.add_node(node_g) 
            return        

        for g in pr.list_nodes():
            if g in node_filter:
                continue 
                
#             print ('item: ', g, type(g), type(pr._wrapped_obj))      
            pr_g = pr[g]
            obj = pr_g._wrapped_obj
            if isinstance(obj, dict):
                node_g = ProjectItem(g, pr, icon='table', icon_style='success')
            elif isinstance(obj, (int, float, str)):
                name_print = '{}: {}'.format(g, pr_g)
                node_g = ProjectItem(g, pr, name_print=name_print, icon='arrow-right', 
                                     icon_style='success')
            elif 'pyiron' in str(type(obj)):
                pyiron_type = str(type(obj)).split('.')[-1][:-2]
                node_g = ProjectItem(g, pr, 
                                     name_print='{} [{}]'.format(pyiron_type, g),
                                     icon='atom', 
                                     icon_style='success')                
            else:    
                node_g = ProjectItem(g, pr, icon='chart-area')
                node_g.icon_style = 'success'
            node_g.observe(self._handle_click, 'selected')
            node.add_node(node_g)
            
        if hasattr(pr, 'list_api'):
            for g in pr.list_api():
                node_g = ProjectItem(g, pr, icon='laptop-code')
                node_g.observe(self._handle_click, 'selected')
                node.add_node(node_g) 
                
        node.loaded = True            

    @_output.capture()
    def _handle_click(self, event):
        self.w_text.clear_output()    # (wait=True)
        node = event['owner']
        pr = node.pr
        self._node_name = event['owner']._pr_name
        pr_new = pr[event['owner']._pr_name]
        print ('Node name: ', self._node_name, type(pr), type(pr_new), 
                hasattr(pr_new, 'list_nodes'), hasattr(pr_new, 'plot3d'))
        
        if hasattr(pr_new, 'plot3d'):
            with self.w_text:
                display(pr_new.plot3d())
            return

        elif hasattr(pr_new, 'list_nodes'):
            if 'data_dict' not in pr_new.list_nodes():
                print ('click: ', type(pr_new))
                self._project = pr
                self._clear_tree()
                self._tree.add_node(node)
                self._open_node(node, pr_new)
                self._back.description = 'Back: {}'.format(pr.name)
                self._back.layout.visibility = 'visible'
                return
        self._show_node(pr_new)
            
    def _show_node(self, node):
        if node is None:
            return

        with self.w_text:
            pw = pyironWrapper(node, node_name=self._node_name)._output_conv()   
            if isinstance(pw, str):
                print (pw)
            else:
                display(pw)
                
class listFiles:
    def __init__(self, obj):
        self._obj = obj
        
    def __getattr__(self, attr):
        if attr in self.__dict__:
            return getattr(self, attr)
        return getattr(self._obj, attr)         
        
    def list_nodes(self):
        return self._obj.list_files()
    
    def list_groups(self):
        return []
        
# wrap pyiron object to provide lacking functionality 
#  -> should be later included in the respective objects
class pyironWrapper:
    api_list = ['job_table', 'list_files', 'get_structure']#, "Input","Output","Images"]
    exclude_extension = ['h5', 'db']
    def __init__(self, pyi_object, node_name=''):
        if isinstance(pyi_object, pyironWrapper):
            self._wrapped_obj = pyi_object._wrapped_obj
        else:        
            self._wrapped_obj = pyi_object
        
        self._obj_list = []
        for attr in self.api_list:
            if hasattr(pyi_object, attr):
                self._obj_list.append(attr) 
        
        self._node_name = node_name
        self.fig = None
        
    def __getattr__(self, attr):
        if attr in self.__dict__:
            return getattr(self, attr)
#         print ('attr: ', attr in self._wrapped_obj.__dict__)
        return getattr(self._wrapped_obj, attr)        

    def list_api(self):
        return self._obj_list
    
    def __getitem__(self, item):
        if item in self.api_list:
            if hasattr(self._wrapped_obj, item):
                new_item = eval('self._wrapped_obj.{}()'.format(item))
                if item == 'list_files':
                    return pyironWrapper(listFiles(self._wrapped_obj))
                return new_item
        return pyironWrapper(self._wrapped_obj[item])
    
    def plot_array(self, val):
        if self.fig is None:
            self.fig, self.ax = plt.subplots()
        else:
            self.ax.clear()

        if val.ndim == 1:
            self.ax.plot(val)
        elif val.ndim == 2:
            if len(val) == 1:
                self.ax.plot(val[0])
            else:
                self.ax.plot(val)
        elif val.ndim == 3:
            self.ax.plot(val[:, :, 0])

        self.ax.set_title(self._node_name)
        return self.ax.figure
    
    def _output_conv(self):
#         print ('_out_conv')
        parent = self._wrapped_obj
        if hasattr(parent, '_repr_html_'):
            return  parent  # ._repr_html_()
        
        node = parent
        eol = os.linesep
#         if self._debug:
        print ('node: ', type(node))
        if isinstance(node, str):
            return (node)
        elif isinstance(node, dict):
            dic = {'Parameter': list(node.keys()), 'Values': list(node.values())}
            return pandas.DataFrame(dic)
        elif isinstance(node, (int, float)):
            return str(node)
        elif isinstance(node, list):
            max_length = 2000   # performance of widget above is extremely poor
            if len(node) < max_length:
                return str(''.join(node))
            else:
                return str(''.join(node[:max_length]) + 
                       eol + ' .... file too long: skipped ....')
        elif isinstance(node, np.ndarray):
            return self.plot_array(node)
        elif 'data_dict' in node.list_nodes():
#             print ('conv_node: ', type(node['data_dict']))
            return pandas.DataFrame(node['data_dict'])        
        
    
#     def _repr_html_(self):
# #         print ('_repr_html_')
#         parent = self._wrapped_obj
#         if hasattr(parent, '_repr_html_'):
#             return  parent  # ._repr_html_()
        
#         node = parent
#         eol = os.linesep
#         print ('node: ', type(node))
#         if isinstance(node, str):
#             return (node)
#         elif isinstance(node, dict):
#             dic = {'Parameter': list(node.keys()), 'Values': list(node.values())}
#             return pandas.DataFrame(dic)
#         elif isinstance(node, (int, float)):
#             return str(node)
#         elif isinstance(node, list):
#             max_length = 2000   # performance of widget above is extremely poor
#             if len(node) < max_length:
#                 return str(''.join(node))
#             else:
#                 return str(''.join(node[:max_length]) + 
#                        eol + ' .... file too long: skipped ....')
#         elif isinstance(node, np.ndarray):
#             return self.plot_array(node)
#         elif 'data_dict' in node.list_nodes():
#             return pandas.DataFrame(node['data_dict'])
            
    def __repr__(self):
        print ('__repr__')
        if hasattr(self._wrapped_obj, '__repr__'):
            return self._wrapped_obj.__repr__()
#         return str(self._wrapped_obj)