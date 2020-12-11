from pyiron_base import InputList

TBR_Metadata_Dict = {
    "Filename": ["", None, "str", "hidden"],
    "Owner": ["Me", None, "str", "normal"],
    "Project": ["SFB", None, "str", "fixed"],
    "PI": [["Someone"], None, "strlist", "normal"],
    "Field": [["Theochem", "Physics"], ["Theochem", "Physics", "Arts", "Whatever"], "strlist", "fixed"],
    "Bench": ["Some_Table", ["Some_Table", "Another Table"], "radio", "normal"],
    "PyironID": ["1", None, "str", "fixed"]
}


class MetaData:
    def __init__(self):
        """ Generic Meta data class """
        self._metadata = InputList(table_name='metadata')
        self._metadate["metadata_scheme"] = "generic"
        self._metadata["metadata_scheme_version"] = 0.1

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, metadata):
        for key, value in metadata.items():
            self._metadata[key] = value


class _MetaDataField:
    """ Simple class to store a single meta data entry. """
    def __init__(self,
                 field_name,
                 content_type="str",
                 status="normal",
                 single_value=True,
                 is_range=False,
                 options=None,
                 extendable=False,
                 value=None
                 ):
        """
        Stores the properties of a single meta data entry.

        Args:
            field_name (str): Name of the meta data field, e.g. 'Owner'
            content_type (str): Type of the content stored: One of "str", "int", "bool", "float", "date"
            status (str): Status of this meta data field: One of "normal", "hidden", "fixed"
            single_value(bool): If True, only a single value may be stored.
            is_range(bool): If True, a range of values is expected (possible for numeric values and date)
            options (list/None): List of options; all entries have to be of type content_type.
            extendable(bool): If True, the list of options may be extended by a new value.
            value(list/content_type/None): The value of the meta data field:
                   May be a list of type content_type or a single instance of this type or None.
        """
        self.name = field_name
        self.content_type = content_type
        self.single_value = single_value
        self.extendable = extendable
        self.value = value
        self.is_range = is_range
        self.status = status
        self.options = options
        self._widget_type = None

    @property
    def widget_type(self):
        """ Returns the type of widget to display the data field. """
        if self._widget_type is None:
            self._derive_widget_type()
        return self._widget_type

    def _derive_widget_type(self):
        """ Helper function to determine optimal widget type. """
        pass
