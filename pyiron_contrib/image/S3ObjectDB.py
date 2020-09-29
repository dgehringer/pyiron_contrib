import boto3
from botocore.client import Config
from pyiron_base import PyironObject
import os
import json

class S3ObjectDB(PyironObject):
    #TODO: implement functions like in hdfio: create_group, remove_group, open, close, get, put (istead of upload)
    #      also include intrinsic functions __stuff__
    def __init__(self, project, config_file = None, config_json = None, group = ''):
        self.project=project
        config = {}
        if config_json is not None:
            config=config_json
        else:
            if config_file is None:
                print('WARN: No config given, trying config.json')
                config_file = './config.json'
            with open(config_file) as json_file:
                config = json.load(json_file)

        s3resource = boto3.resource('s3', 
            config=Config(s3={'addressing_style': 'path'}),
            aws_access_key_id=config['access_key'],
            aws_secret_access_key=config['secret_key'],
            endpoint_url=config['endpoint']
        )
        bucket_name = config['bucket']
        # Now, the bucket object
        self.bucket = s3resource.Bucket(bucket_name)
        self._set_group(group)

    def print_bucket_info(self): 
        print('Bucket name: {}'.format(self.bucket.name))

    def list_groups(self):
        """
        Return a list of 'directories' ( string followed by / )

        Returns:
            :class:`list`
        """
        groups = []
        group_path_len=len(self.group.split('/'))-1
        for obj in self._list_objects():
            rel_obj_path_spl=obj.split('/')[group_path_len:]
            if len(rel_obj_path_spl) > 1:
                groups.append(rel_obj_path_spl[0])
        return groups

    def list_nodes(self):
        """
        Return a list of 'files' ( string not followed by / )

        Returns:
            :class:`list`
        """
        nodes = []
        group_path_len = len(self.group.split('/')) - 1
        for obj in self._list_objects():
            rel_obj_path_spl = obj.split('/')[group_path_len:]
            if len(rel_obj_path_spl) == 1:
                nodes.append(rel_obj_path_spl[0])
        return nodes

    def _set_group(self, group):
        if len(group)==0:
            self.group = group
        elif group[-1]== '/':
            self.group = group
        else:
            self.group = group + '/'
        
    def upload(self,files):
        for file in files:
            [path,f]=os.path.split(file)
            def printBytes(x):
                print('{} {}/{} bytes'.format(f, x, s))
            s = os.path.getsize(file)
            self.bucket.upload_file(
                file,
                self.group + f,
                Callback=printBytes
            )
    def _list_objects(self):
        l=[]
        for obj in self.bucket.objects.filter(Prefix=self.group):
            l.append(obj.key)
        return l

    def print_fileinfo(self):
        # prints the filename, last modified date and size for _all_ files in the current group
        for obj in self.bucket.objects.filter(Prefix=self.group):
            print('{} {} {} bytes'.format(obj.key, obj.last_modified, obj.size))

    def _list_all_files_of_bucket2(self):
        for obj in self.bucket.objects.all():
            print('{} {} {} bytes'.format(obj.key, obj.last_modified, obj.size))


    def _del_group(self,prefix=None):
        if prefix==None:
            prefix=self.group
        print('\nDeleting all objects with sample prefix {}/{}.'.format(self.bucket.name, prefix))
        delete_responses = self.bucket.objects.filter(Prefix=prefix).delete()
        for delete_response in delete_responses:
            for deleted in delete_response['Deleted']:
                print('\t Deleted: {}'.format(deleted['Key']))

"""
Some infos about the bucket object:

o.bucket= self.bucket   has the following   options:
--------------------------------------------------------------------------------------------------------------
o.bucket.Acl(                         o.bucket.Website(                     o.bucket.multipart_uploads
o.bucket.Cors(                        o.bucket.copy(                        o.bucket.name
o.bucket.Lifecycle(                   o.bucket.create(                      o.bucket.object_versions
o.bucket.LifecycleConfiguration(      o.bucket.creation_date                o.bucket.objects
o.bucket.Logging(                     o.bucket.delete(                      o.bucket.put_object(
o.bucket.Notification(                o.bucket.delete_objects(              o.bucket.upload_file(
o.bucket.Object(                      o.bucket.download_file(               o.bucket.upload_fileobj(
o.bucket.Policy(                      o.bucket.download_fileobj(            o.bucket.wait_until_exists(
o.bucket.RequestPayment(              o.bucket.get_available_subresources(  o.bucket.wait_until_not_exists(
o.bucket.Tagging(                     o.bucket.load(
o.bucket.Versioning(                  o.bucket.meta

o.bucket.objects   has the following  options:
--------------------------------------------------------------------------------------------------------------
o.bucket.objects.all(        o.bucket.objects.filter(     o.bucket.objects.limit(      o.bucket.objects.pages(
o.bucket.objects.delete(     o.bucket.objects.iterator(   o.bucket.objects.page_size(

o.bucket.Object  is an object of the object store. It is identified by a key, i.e. the full path + file name in the bucket.
Actually, there is no such thing as directories inside the bucket. '/' is a valid character in filenames and we use this fact 
to separate files into directories. 
obj=o.bucket.Object(/path/to/file)  has the following option:
--------------------------------------------------------------------------------------------------------------
obj.Acl(                           obj.download_fileobj(              obj.put(
obj.Bucket(                        obj.e_tag                          obj.reload(
obj.MultipartUpload(               obj.expiration                     obj.replication_status
obj.Version(                       obj.expires                        obj.request_charged
obj.accept_ranges                  obj.get(                           obj.restore
obj.bucket_name                    obj.get_available_subresources(    obj.restore_object(
obj.cache_control                  obj.initiate_multipart_upload(     obj.server_side_encryption
obj.content_disposition            obj.key                            obj.sse_customer_algorithm
obj.content_encoding               obj.last_modified                  obj.sse_customer_key_md5
obj.content_language               obj.load(                          obj.ssekms_key_id
obj.content_length                 obj.meta                           obj.storage_class
obj.content_type                   obj.metadata                       obj.upload_file(
obj.copy(                          obj.missing_meta                   obj.upload_fileobj(
obj.copy_from(                     obj.object_lock_legal_hold_status  obj.version_id
obj.delete(                        obj.object_lock_mode               obj.wait_until_exists(
obj.delete_marker                  obj.object_lock_retain_until_date  obj.wait_until_not_exists(
obj.download_file(                 obj.parts_count                    obj.website_redirect_location

with obj.get() one gets the object.
with obj.download_file('Filename') one downloads the associated file to 'Filename'

getobj=o.bucket.Object(object_key).get() has the following options:
--------------------------------------------------------------------------------------------------------------
getobj.clear(       getobj.fromkeys(    getobj.items(       getobj.pop(         getobj.setdefault(  getobj.values(
getobj.copy(        getobj.get(         getobj.keys(        getobj.popitem(     getobj.update(

"""
