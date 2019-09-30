from fbs_runtime.application_context.PySide2 import ApplicationContext, cached_property
from PySide2.QtCore import Qt, Signal
from PySide2.QtGui import QColor, QCursor
from PySide2.QtWidgets import QWidget, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QTreeWidget, QTreeWidgetItem, QDialogButtonBox, QDialog, QLineEdit, QAbstractItemView, QMenuBar, QMenu, QAction, QDialog, QMessageBox, QInputDialog, QLabel
from oci_manager import oci_manager, UploadId
from config import ConfigWindow
from progress import ProgressWindow
from util import get_filesize
from upload_thread import UploadThread
from download_thread import DownloadThread
from rename import RenameWindow
from tree import Tree, TreeWidgetItem
import sys
import os
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
f_handler = logging.FileHandler(os.path.expanduser(os.path.join('~', '.oci', 'object_storage.log')))
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
f_handler.setFormatter(f_format)
logger.addHandler(f_handler)

class AppContext(ApplicationContext):
    def run(self):
        try:
            # stylesheet = self.get_resource('styles.qss')
            #self.app.setStyleSheet(open(stylesheet).read())
            self.window.show()
            return self.app.exec_()
        except Exception as e:
            logger.exception("Exception occured")
            raise e
    @cached_property
    def window(self):
        return MainWindow(self.menu_bar, self.central, self.config)
    @cached_property
    def menu_bar(self):
        return MainMenu()
    @cached_property
    def central(self):
        return CentralWidget()
    @cached_property
    def config(self):
        return ConfigWindow('DEFAULT')


class MainWindow(QMainWindow):
    def __init__(self, main_menu, central_widget, config_window):
        """
        Wrapper to connect the central widget and menu bar together and also the config window.

        :param main_menu: The menu toolbar on the top of the application
        :type main_menu: class 'Menu'
        :param central_widget: The central widget of the main window
        :type central_widget: class 'CentralWidget'
        :param config_window: The window with holds the config settings
        :type config_window: class 'config.ConfigWindow'
        """
        super().__init__()
        
        self.central_widget = central_widget
        self.menubar = main_menu
        self.config_window = config_window
        self.config_window.main_window = self
        self.menubar.config_window = self.config_window

        self.menubar.compartment_view.triggered.connect(self.central_widget.compartment_tree.toggle)
        self.menubar.bucket_view.triggered.connect(self.central_widget.bucket_tree.toggle)
        self.menubar.object_view.triggered.connect(self.central_widget.obj_tree.toggle)
        self.menubar.upload_action.triggered.connect(self.central_widget.select_files)

        self.setCentralWidget(self.central_widget)
        self.setWindowTitle(self.central_widget.windowTitle())
        self.setMenuBar(self.menubar)

    
    
    def change_profile(self, new_profile):
        """
        Changes the current OCI profile for the CentralWidget class. Can be called by the ConfigWindow class

        :param new_profile: Profile containing the required parameters needed for OCI authentication
        :type new_profile: dict

        TODO: Refactor code to better adhere to Qt signal/slot design pattern
        """
        print(new_profile)
        self.central_widget.refresh(new_profile)

    def change_title(self):
        """
        Changes the title of the MainWindow by reading from the title of the CentralWidget. Can be called by the CentralWidget class

        TODO: Refactor code to better adhere to Qt signal/slot design pattern
        """
        self.setWindowTitle(self.central_widget.windowTitle())
    



class CentralWidget(QWidget):
    
    def __init__(self):
        """
        The central hub for the application. Contains the tree views for compartments, buckets, and objects.
        Has buttons for uploading files and creating buckets
        """
        super().__init__()
        self.setWindowTitle("OCI Object Storage: Not Connected")
        self.setMinimumSize(800, 600)
        self.profile = 'DEFAULT'
        self.oci_manager = oci_manager(profile = self.profile)

        try:
            self.compartment_tree = self.get_compartment_tree()
        except:
            print('Error: Failure to establish connection')
            self.compartment_tree = self.get_placeholder_tree('Compartments', 'Error: Failure to establish connection')
        else:
            self.setWindowTitle("OCI Object Storage: {}".format(self.oci_manager.get_namespace()))

        self.bucket_tree = self.get_placeholder_tree('Buckets', 'No compartment selected')
        self.obj_tree = self.get_placeholder_tree('Objects', 'No bucket selected')
        self.obj_tree.setHeaderLabels(['Objects', 'Size'])
        self.obj_tree.resizeColumnToContents(0)

        self.bucket_tree.itemClicked.connect(self.select_bucket)

        button = QPushButton('Upload Files')
        button.clicked.connect(self.select_files)

        button2 = QPushButton('New Bucket')
        button2.clicked.connect(self.create_bucket_prompt)

        button3 = QPushButton('Refresh')
        button3.clicked.connect(self.refresh)

        buttonBox = QDialogButtonBox()
        buttonBox.setOrientation(Qt.Vertical)
        buttonBox.addButton(button, QDialogButtonBox.ActionRole)
        buttonBox.addButton(button2, QDialogButtonBox.ActionRole)
        buttonBox.addButton(button3, QDialogButtonBox.ActionRole)
        
        self.layout = QHBoxLayout()
        self.layout.addWidget(buttonBox)

        self.layout.setAlignment(buttonBox, Qt.AlignHCenter)
        self.layout.addWidget(self.compartment_tree)
        self.layout.addWidget(self.bucket_tree)
        self.layout.addWidget(self.obj_tree)
        self.setLayout(self.layout)

        self.upload_threads = {}
        self.upload_thread_count = 0
        self.progress_threads = {}
        self.progress_thread_count = 0

    def refresh(self, profile=None, prev_compartment=None, prev_bucket=None):
        """
        Fetchs all TreeWidgets and window title information using the given profile

        :param profile: Profile containing the required parameters needed for OCI authentication
        :type profile: dict
        :param prev_compartment: The compartment previously activated. Used to reselect the compartment after refresh
        :type prev_compartment: QTreeItemWidget
        :param prev_bucket: The bucket previously activated. Used to reselect the bucket after the refresh
        :type prev_bucket: QTreeItemWidget

        TODO: Inserting paremeters prev_compartment and prev_bucket do not work as intended. Find a way to keep the activated item state after refresh
        """
        if profile:
            self.profile = profile
        self.oci_manager = oci_manager(profile=self.profile)

        self.setWindowTitle("OCI Object Storage: {}".format(self.oci_manager.get_namespace()))
        self.parentWidget().change_title()

        try:
            n1 = self.get_compartment_tree()
        except:
            print('Error: Failure to establish connection')
            n1 = self.get_placeholder_tree('Compartments', 'Error: Failure to establish connection')

        n2 = self.get_placeholder_tree('Buckets', 'No compartment selected')
        n3 = self.get_placeholder_tree('Objects', 'No bucket selected')

        self.layout.removeItem(self.layout.itemAt(3))
        self.obj_tree.setParent(None)
        self.obj_tree = n3
        self.layout.insertWidget(3, self.obj_tree)

        self.layout.removeItem(self.layout.itemAt(2))
        self.bucket_tree.setParent(None)
        self.bucket_tree = n2
        self.layout.insertWidget(2, self.bucket_tree)

        self.layout.removeItem(self.layout.itemAt(1))
        self.compartment_tree.setParent(None)
        self.compartment_tree = n1
        self.layout.insertWidget(1, self.compartment_tree)

        self.bucket_tree.itemClicked.connect(self.select_bucket)

        if prev_compartment:
            self.select_compartment(self.compartment_tree.itemAt(prev_compartment))
        if prev_bucket:
            self.select_bucket(self.bucket_tree.itemAt(prev_bucket))

    def create_bucket_prompt(self):
        """
        Open a prompt to create a bucket in the activated compartment
        """

        def create_bucket():
            print(self.bucket_form.line.text())
            namespace = self.oci_manager.get_namespace()
            create_bucket_details = self.oci_manager.create_bucket_details(name=self.bucket_form.line.text(), compartment_id=compartment[-1].text(1))
            r = self.oci_manager.get_os().create_bucket(namespace, create_bucket_details)
            self.bucket_form.hide()
            self.select_compartment(compartment[-1])

        self.bucket_form = CreateBucketForm()
        self.bucket_form.button.clicked.connect(create_bucket)

        compartment = self.compartment_tree.selectedItems()
        if compartment:
            self.bucket_form.show()
        else:
            print("Must choose a compartment")

    def select_files(self):
        """
        Opens a file navigator window to choose files to upload into the currently activated bucket
        """
        buckets = self.bucket_tree.selectedItems()
        if buckets:
            files = QFileDialog.getOpenFileNames(self, "Select one or more files to open")
            print(files)
            print(type(files))
            for bucket in buckets:
                self.upload_files(files, bucket.text(0))
                self.select_bucket(bucket)
        else:
            print("Must choose a bucket")        

    def download_files(self, objects, filesizes, bucket_name):

        c = self.progress_thread_count
        self.progress_thread_count += 1
        self.upload_thread_count += 1

        progress_thread = ProgressWindow((objects, 'All files'), filesizes, c, download=True)
        download_thread = DownloadThread(objects, bucket_name, self.oci_manager, c)
        
        download_thread.file_downloaded.connect(progress_thread.next_file)
        download_thread.bytes_downloaded.connect(progress_thread.set_progress)
        download_thread.all_files_downloaded.connect(self.delete_threads)
        progress_thread.cancel_signal.connect(self.thread_cancelled)
        download_thread.download_failed.connect(progress_thread.retry_handler)
        progress_thread.retry.clicked.connect(download_thread.start)

        self.progress_threads[c] = progress_thread
        self.upload_threads[c] = download_thread

        self.progress_threads[c].show()
        self.upload_threads[c].start()


    
    def upload_files(self, files, bucket_name):
        """
        Uploads files to a bucket in OCI Object Storage. Can be called from the select_files function.

        :param files: A tuple of files. First element is a list of absolute paths to the files. Second element is the mimetype of files
        :type files: tuple
        :param bucket_name: The name of bucket to upload file(s) to in OCI
        :type bucket_name: string

        """
        
        filesizes = []

        for file in files[0]:
            filesizes.append(get_filesize(file))

        c = self.progress_thread_count
        self.progress_thread_count += 1
        self.upload_thread_count += 1

        progress_thread = ProgressWindow(files, filesizes, c)
        upload_thread = UploadThread(files, bucket_name, self.oci_manager, filesizes, c)
        upload_thread.file_uploaded.connect(progress_thread.next_file)
        upload_thread.file_uploaded.connect(self.file_uploaded)
        upload_thread.bytes_uploaded.connect(progress_thread.set_progress)
        upload_thread.all_files_uploaded.connect(self.delete_threads)
        upload_thread.upload_failed.connect(progress_thread.retry_handler)
        progress_thread.cancel_signal.connect(self.thread_cancelled)
        progress_thread.retry.clicked.connect(upload_thread.start)
        # progress_thread.setMinimumHeight(50)
        self.progress_threads[c] = progress_thread
        self.upload_threads[c] = upload_thread

        self.progress_threads[c].show()
        self.upload_threads[c].start()

    def file_uploaded(self, filename, filesize, bucket_name, filesize_bits):
        """
        When a file is uploaded then we add the filename and the filesize to the object tree view

        :param filename: The name of the file
        :type filename: string
        :param filesize: The filesize in format of numeric then abbreviated units e.g '128 KB'
        :type filesize: string

        """
        print(filename, filesize, "Uploaded")
        items = [item.text(0) for item in self.bucket_tree.selectedItems()]

        if items and items[0] == bucket_name:
            obj_tree_item = TreeWidgetItem(self.obj_tree)
            obj_tree_item.setText(0, filename)
            obj_tree_item.setText(1, filesize)
            obj_tree_item.setText(2, str(filesize_bits))
    
    def delete_threads(self, thread_id):
        """
        Deletes the upload thread from the dictionary of upload threads when it completes

        :param thread_id: The id given to the thread upon creation
        :type thread_id: int
        """
        print("All files uploaded. Deleting upload thread")
        if thread_id in self.upload_threads:
            del self.upload_threads[thread_id]
    
    
    def thread_cancelled(self, thread_id):
        """
        Deletes the upload thread and progress window threads from their respective dictionaries when the job is cancelled

        :param thread_id: The id given to the threads upon creation
        :type thread_id: int
        """

        self.upload_threads[thread_id].stop()
        if thread_id in self.upload_threads:
            del self.upload_threads[thread_id]
        if thread_id in self.progress_threads:
            del self.progress_threads[thread_id]

    def get_compartment_tree(self):
        """
        Using the current profile, constructs a tree widget that displays a directory of compartments and subcompartments

        :return: A tree widget that displays a directory of compartments and subcompartments
        :rtype :class: QTreeWidget
        """

        root = self.oci_manager.get_tenancy()
        compartments = self.oci_manager.get_id().list_compartments(root, compartment_id_in_subtree=True)

        data = compartments.data

        compartment_dic = {}
        hierarchy = {}
        tree_dic = {}

        while compartments.next_page:
            compartments = self.oci_manager.get_id().list_compartments(root, compartment_id_in_subtree=True, page=compartments.next_page)
            data += compartments.data

        for compartment in data:
            if (compartment.lifecycle_state == 'ACTIVE'):
                compartment_dic[compartment.id] = compartment
                if compartment.compartment_id in hierarchy:
                    hierarchy[compartment.compartment_id] += [compartment.id]
                else:
                    hierarchy[compartment.compartment_id] = [compartment.id]

        tree_widget = Tree()
        tree_widget.setHeaderLabels(['Compartments', 'OCID'])
        tree_dic[root] = TreeWidgetItem(tree_widget)
        tree_dic[root].setText(0, '(root)')
        tree_dic[root].setText(1, root)

        stack = [root]
        while stack:
            compartment_id = stack.pop()
            parent_tree = tree_dic[compartment_id]
            for child_id in hierarchy[compartment_id]:
                child_tree = TreeWidgetItem(parent_tree)
                child_tree.setText(0, compartment_dic[child_id].name)
                child_tree.setText(1, child_id)
                tree_dic[child_id] = child_tree
                if child_id in hierarchy:
                    stack.append(child_id)
    
        tree_widget.itemClicked.connect(self.select_compartment)
        tree_widget.setColumnHidden(1, True)
        return tree_widget
    
    def select_compartment(self, item):
        """
        Slot to populate the bucket and object list view when a compartment is activated

        :param item: The selected compartment tree item
        :type item: QTreeWidgetItem
        """
        if not item.isDisabled():
            # self.layout.removeItem(self.layout.itemAt(2))
            # self.bucket_tree.setParent(None)
            self.get_buckets_tree_safe(item.text(1))
            # self.layout.insertWidget(2, self.bucket_tree)
            # self.layout.removeItem(self.layout.itemAt(3))
            # self.obj_tree.setParent(None)
            self.get_objects_tree_safe(None)
            # self.layout.insertWidget(3, self.obj_tree)
    
    def get_buckets_tree(self, ocid):
        """
        Constructs a tree widget that displays a list of buckets

        :param ocid: The OCID of the compartment
        :type ocid: string

        :return: A tree widget that displays a list of buckets
        :rtype :class: QTreeWidget
        """
        namespace = self.oci_manager.get_namespace()
        tree_widget = Tree()
        tree_widget.setHeaderLabel('Buckets')
        data = []
        try:
            data = self.oci_manager.get_os().list_buckets(namespace, ocid).data
        except:
            print("You do not have authorization to perform this request, or the requested resource could not be found")
            bucket_tree = TreeWidgetItem(tree_widget)
            bucket_tree.setText(0, 'You do not have authorization to perform this request, or the requested resource could not be found')
            bucket_tree.setTextColor(0, QColor(220,220,220))
        finally:
            if not data:
                bucket_tree = TreeWidgetItem(tree_widget)
                bucket_tree.setText(0, 'Compartment contains no buckets')
                bucket_tree.setTextColor(0, QColor(220,220,220))
            else:
                for bucket in data:
                    print(bucket.name)
                    bucket_tree = TreeWidgetItem(tree_widget)
                    bucket_tree.setText(0, bucket.name)
                tree_widget.itemClicked.connect(self.select_bucket)

        return tree_widget
    
    def get_buckets_tree_safe(self, ocid):
        """
        Constructs a tree widget that displays a list of buckets

        :param ocid: The OCID of the compartment
        :type ocid: string

        :return: A tree widget that displays a list of buckets
        :rtype :class: QTreeWidget
        """
        namespace = self.oci_manager.get_namespace()
        self.bucket_tree.clear()
        data = []
        try:
            data = self.oci_manager.get_os().list_buckets(namespace, ocid).data
        except:
            print("You do not have authorization to perform this request, or the requested resource could not be found")
            bucket_tree_item = TreeWidgetItem(self.bucket_tree)
            bucket_tree_item.setText(0, 'You do not have authorization to perform this request, or the requested resource could not be found')
            bucket_tree_item.setTextColor(0, QColor(220,220,220))
            bucket_tree_item.setDisabled(True)
        finally:
            if not data:
                bucket_tree_item = TreeWidgetItem(self.bucket_tree)
                bucket_tree_item.setText(0, 'Compartment contains no buckets')
                bucket_tree_item.setTextColor(0, QColor(220,220,220))
                bucket_tree_item.setDisabled(True)
            else:
                for bucket in data:
                    print(bucket.name)
                    bucket_tree_item = TreeWidgetItem(self.bucket_tree)
                    bucket_tree_item.setText(0, bucket.name)
                # self.bucket_tree.itemClicked.connect(self.select_bucket)
    
    def select_bucket(self, item):
        """
        Slot to populate the object list view when a bucket is activated

        :param item: The selected bucket tree item
        :type item: QTreeWidgetItem
        """
        if not item.isDisabled():
            # self.layout.removeItem(self.layout.itemAt(3))
            # self.obj_tree.setParent(None)
            self.get_objects_tree_safe(item.text(0))
            # self.layout.insertWidget(3, self.obj_tree)
    
    def get_objects_tree(self, bucket_name):
        """
        Constructs a tree widget that displays a list of objects in a bucket

        :param bucket_name: The name of the bucket
        :type bucket_name: string

        :return: A tree widget that displays a directory of compartments and subcompartments
        :rtype :class: QTreeWidget
        """
        namespace = self.oci_manager.get_namespace()

        tree_widget = Tree(accept_drop=True, bucket_name=bucket_name, oci_manager=self.oci_manager)
        tree_widget.setColumnCount(2)
        tree_widget.setHeaderLabels(['Objects', 'Size'])

        byte_type = ['KB', 'MB', 'GB', 'TB', 'PB']

        data = self.oci_manager.get_os().list_objects(namespace, bucket_name, fields='size').data.objects

        for obj in data:
            print(obj.name)
            obj_tree_item = TreeWidgetItem(tree_widget)
            obj_tree_item.setText(0, obj.name)
            byte_type_pointer = 0
            byte_size = obj.size/1024.0
            while byte_size > 1024:
                byte_size = byte_size/1024.0
                byte_type_pointer += 1
            byte_size = round(byte_size, 2)
            obj_tree_item.setText(1, "{} {}".format(str(byte_size), byte_type[byte_type_pointer]))

        return tree_widget

    def get_objects_tree_safe(self, bucket_name):
        """
        Constructs a tree widget that displays a list of objects in a bucket

        :param bucket_name: The name of the bucket
        :type bucket_name: string

        :return: A tree widget that displays a directory of compartments and subcompartments
        :rtype :class: QTreeWidget
        """
        self.obj_tree.clear()
        if bucket_name:
            if not self.obj_tree.accept_drop:
                self.obj_tree.accept_drop = True
                self.obj_tree.object_tree_init()
            if not self.obj_tree.oci_manager:
                self.obj_tree.oci_manager = self.oci_manager
            self.obj_tree.bucket_name = bucket_name
            namespace = self.oci_manager.get_namespace()
            byte_type = ['KB', 'MB', 'GB', 'TB', 'PB']

            data = self.oci_manager.get_os().list_objects(namespace, bucket_name, fields='size').data.objects
            for obj in data:
                print(obj.name)
                obj_tree_item = TreeWidgetItem(self.obj_tree)
                obj_tree_item.setText(0, obj.name)
                byte_type_pointer = 0
                byte_size = obj.size/1024.0
                while byte_size > 1024:
                    byte_size = byte_size/1024.0
                    byte_type_pointer += 1
                byte_size = round(byte_size, 2)
                obj_tree_item.setText(1, "{} {}".format(str(byte_size), byte_type[byte_type_pointer]))
                obj_tree_item.setText(2, str(obj.size))
        else:
            tree_item = TreeWidgetItem(self.obj_tree)
            tree_item.setText(0, "No bucket selected")
            tree_item.setTextColor(0, QColor(220,220,220))
            tree_item.setDisabled(True)
            self.obj_tree.accept_drop = False
            
    def get_placeholder_tree(self, header, text):
        """
        Create a placeholder tree widget for situations where real object storage information is not fetched

        :param header: The header of the tree widget
        :type header: string
        :param text: The tree item text to display in tree
        :type text: string

        :return: A placeholder tree with greyed text
        :rtype: QTreeWidget
        """
        tree_widget = Tree()
        tree_widget.setHeaderLabel(header)
        tree_item = TreeWidgetItem(tree_widget)
        tree_item.setText(0, text)
        tree_item.setTextColor(0, QColor(220,220,220))
        tree_item.setDisabled(True)
        return tree_widget


class CreateBucketForm(QDialog):
    def __init__(self, parent=None):
        """
        A CreateBucketForm is a widget that prompts users with a dialog and button to create a new bucket
        """
        super(CreateBucketForm, self).__init__(parent)
        self.setWindowTitle("Create Bucket")
        layout = QVBoxLayout()
        self.line = QLineEdit()
        self.line.setPlaceholderText('Bucket name')
        self.button = QPushButton("Create")
        layout.addWidget(self.line)
        layout.addWidget(self.button)
        self.setLayout(layout)


class MainMenu(QMenuBar):

    toggle_compartment = Signal()
    upload_files = Signal()

    def __init__(self, config_window=None):
        """
        Widget to display menu actions at the top of the application

        :param config_window: ConfigWindow widget to display when the Profile Settings action is clicked
        :type: :class: 'config.ConfigWindow'
        """
        super(MainMenu, self).__init__()
        self.config_window = config_window
        # self.config_window.setParent(self)
        self.setNativeMenuBar(True)
        test_menu = self.addMenu('')
        # for text in ["About", "Preferences"]:
        #     action = test_menu.addAction(text)
        #     action.setMenuRole(QAction.ApplicationSpecificRole)
        
        self.about_action = test_menu.addAction("About")
        self.about_action.triggered.connect(self.about)


        self.file_menu = self.addMenu('&File')
        self.upload_action = self.file_menu.addAction("Upload File(s)")
        # self.file_menu.triggered.connect(self.upload_file_handler)
        self.edit_menu = self.addMenu('&Edit')
        profile_action = self.edit_menu.addAction("Profile Settings")
        profile_action.triggered.connect(self.settings)
        self.view_menu = self.addMenu('&View')

        self.compartment_view = self.view_menu.addAction("Compartments")
        self.compartment_view.setCheckable(True)
        self.compartment_view.setChecked(True)

        self.bucket_view = self.view_menu.addAction("Buckets")
        self.bucket_view.setCheckable(True)
        self.bucket_view.setChecked(True)
        
        self.object_view = self.view_menu.addAction("Objects")
        self.object_view.setCheckable(True)
        self.object_view.setChecked(True)

    def about(self):
        self.about_box = QDialog()
        self.about_box.setWindowTitle("About")
        text = QLabel()
        text.setText\
        ("This is an UNOFFICIAL desktop client to interact with \
        \nthe Oracle Cloud Infrastructure Object Storage service.\
        \nPlease use at your own discretion.\
        \nThis application is not affiliated with Oracle.\
        \nNot available for resale or commercial use.\
        \n\
        \nWritten by Alexander Ros\
        \n\
        \n Version 0.1.0")
        text.setAlignment(Qt.AlignHCenter)
        layout = QVBoxLayout()
        layout.addWidget(text)
        self.about_box.setLayout(layout)
        self.about_box.show()

    def settings(self):
        """
        Slot to display the ConfigWindow widget when the Profile Settings action is triggered
        """
        if not self.config_window:
            self.config_window = ConfigWindow('DEFAULT')
        self.config_window.show()
    
    def change_profile(self, new_profile):
        """
        Change the profile
        """
        self.parentWidget().change_profile(new_profile)
    
    def upload_file_handler(self):
        self.upload_files.emit()



if __name__ == '__main__':
    logger.info("Application starting")
    appctxt = AppContext()
    exit_code = appctxt.run()
    logger.info("Application closing")
    sys.exit(exit_code)