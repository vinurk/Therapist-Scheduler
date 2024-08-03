import os
import sys

from PySide2.QtCore import  QMetaObject
from PySide2.QtUiTools import QUiLoader
from PySide2 import QtGui, QtCore, QtWidgets
import pickle
import algo_v2
import mysql.connector as mc

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))



class UiLoader(QUiLoader):

    def __init__(self, baseinstance, customWidgets=None):

        QUiLoader.__init__(self, baseinstance)
        self.baseinstance = baseinstance
        self.customWidgets = customWidgets

    def createWidget(self, class_name, parent=None, name=''):

        if parent is None and self.baseinstance:
            # supposed to create the top-level widget, return the base instance
            # instead
            return self.baseinstance

        else:
            if class_name in self.availableWidgets():
                # create a new widget for child widgets
                widget = QUiLoader.createWidget(self, class_name, parent, name)

            else:
                # if not in the list of availableWidgets, must be a custom widget
                # this will raise KeyError if the user has not supplied the
                # relevant class_name in the dictionary, or TypeError, if
                # customWidgets is None
                try:
                    widget = self.customWidgets[class_name](parent)

                except (TypeError, KeyError) as e:
                    raise Exception('No custom widget ' + class_name + ' found in customWidgets param of UiLoader __init__.')

            if self.baseinstance:
                # set an attribute for the new child widget on the base
                # instance, just like PyQt4.uic.loadUi does.
                setattr(self.baseinstance, name, widget)

                # this outputs the various widget names, e.g.
                # sampleGraphicsView, dockWidget, samplesTableView etc.
                #print(name)

            return widget


def loadUi(uifile, baseinstance=None, customWidgets=None,
           workingDirectory=None):

    loader = UiLoader(baseinstance, customWidgets)

    if workingDirectory is not None:
        loader.setWorkingDirectory(workingDirectory)

    widget = loader.load(uifile)
    QMetaObject.connectSlotsByName(widget)
    return widget

def clickable(widget):

    class Filter(QtCore.QObject):
     
        clicked = QtCore.Signal()
           
        def eventFilter(self, obj, event):
           
            if obj == widget:
                if event.type() == QtCore.QEvent.MouseButtonRelease:
                    if obj.rect().contains(event.pos()):
                        self.clicked.emit()
                        # The developer can opt for .emit(obj) to get the object within the slot.
                        return True
            
            return False

    filter = Filter(widget)
    widget.installEventFilter(filter)
    return filter.clicked

class CheckableComboBox(QtWidgets.QComboBox):
    
    # Subclass Delegate to increase item height
    class Delegate(QtWidgets.QStyledItemDelegate):
        def sizeHint(self, option, index):
            size = super().sizeHint(option, index)
            size.setHeight(20)
            return size

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make the combo editable to set a custom text, but readonly
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)

        self.currentOptions = []
        
        # Make the lineedit the same color as QPushButton
        palette = QtWidgets.QApplication.instance().palette()
        palette.setBrush(QtGui.QPalette.Base, palette.button())
        self.lineEdit().setPalette(palette)

        # Use custom delegate
        self.setItemDelegate(CheckableComboBox.Delegate())

        # Update the text when an item is toggled
        self.model().dataChanged.connect(self.updateText)

        # Hide and show popup when clicking the line edit
        self.lineEdit().installEventFilter(self)
        self.closeOnLineEditClick = False

        # Prevent popup from closing when clicking on an item
        self.view().viewport().installEventFilter(self)

    def resizeEvent(self, event):
        # Recompute text to elide as needed
        self.updateText()
        super().resizeEvent(event)

    def eventFilter(self, object, event):

        if object == self.lineEdit():
            if event.type() == QtCore.QEvent.MouseButtonRelease:
                if self.closeOnLineEditClick:
                    self.hidePopup()
                else:
                    self.showPopup()
                return True
            return False

        if object == self.view().viewport():
            if event.type() == QtCore.QEvent.MouseButtonRelease:
                index = self.view().indexAt(event.pos())
                item = self.model().item(index.row())

                if item.checkState() == QtCore.Qt.Checked:
                    item.setCheckState(QtCore.Qt.Unchecked)
                else:
                    item.setCheckState(QtCore.Qt.Checked)
                return True
        return False

    def showPopup(self):
        super().showPopup()
        # When the popup is displayed, a click on the lineedit should close it
        self.closeOnLineEditClick = True

    def hidePopup(self):
        super().hidePopup()
        # Used to prevent immediate reopening when clicking on the lineEdit
        self.startTimer(100)
        # Refresh the display text when closing
        self.updateText()

    def timerEvent(self, event):
        # After timeout, kill timer, and reenable click on line edit
        self.killTimer(event.timerId())
        self.closeOnLineEditClick = False

    def updateText(self):
        texts = []
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == QtCore.Qt.Checked:
                texts.append(self.model().item(i).text())
        text = ", ".join(texts)

        # Compute elided text (with "...")
        metrics = QtGui.QFontMetrics(self.lineEdit().font())
        font11 = QtGui.QFont()
        font11.setPointSize(12)
        elidedText = metrics.elidedText(text, QtCore.Qt.ElideRight, self.lineEdit().width())
        self.lineEdit().setText(elidedText)
        self.lineEdit().setFont(font11)

    def addItem(self, text, data=None):
        self.currentOptions.append(text)
        item = QtGui.QStandardItem()
        item.setText(text)
        if data is None:
            item.setData(text)
        else:
            item.setData(data)
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
        item.setData(QtCore.Qt.Unchecked, QtCore.Qt.CheckStateRole)
        self.model().appendRow(item)

    def addItems(self, texts, datalist=None):
        
        for i, text in enumerate(texts):
            try:
                data = datalist[i]
            except (TypeError, IndexError):
                data = None
            self.addItem(text, data)


    def clear(self):
        super().clear()
        self.currentOptions.clear()


    def clear_selection(self):
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == QtCore.Qt.Checked:
                self.model().item(i).setCheckState(QtCore.Qt.Unchecked)
        

    def currentData(self):
        # Return the list of selected items data
        res = []
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == QtCore.Qt.Checked:
                res.append(self.model().item(i).data())
        return res


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        loadUi(os.path.join(SCRIPT_DIRECTORY, 'algo_gui.ui'), self)
        self.options_chosen = [[self.dashboard_opt,True],[self.job_details,False],[self.therapist_details,False],[self.patient_detail,False],[self.setting_opt,False],[self.about_opt,False]]

    
        self.db_details_ready = False
        self.db_detail_save_button.clicked.connect(self.on_click_db_detail_save_button)

        if os.path.exists(os.path.join(SCRIPT_DIRECTORY,"db_info.dat")):
            db_dat_file = open("db_info.dat","rb")
            db_dat_list = pickle.load(db_dat_file)
            self.MYSQL_HOST,self.MYSQL_USER,self.MYSQL_PASSWORD,self.MYSQL_DB = db_dat_list[0],db_dat_list[1],db_dat_list[2],db_dat_list[3]
            self.db_details_ready = True
            if not self.check_connection():
                self.ready_gui()
                db_dat_file.close()
            else:
                self.select_option(4)
        else:
            self.select_option(4)
            

        #https://gis.stackexchange.com/questions/350148/qcombobox-multiple-selection-pyqt5
        #https://stackoverflow.com/questions/50899177/pyqt-change-the-position-in-the-gridlayout-for-inner-qvboxlayout
        

    
    def check_connection(self):
        try:
            self.db_connection = mc.connect(host=self.MYSQL_HOST, user=self.MYSQL_USER,
                    password=self.MYSQL_PASSWORD, database=self.MYSQL_DB)
        except Exception as e:
            return False

    def ready_gui(self):
        if self.db_details_ready:
            font11 = QtGui.QFont()
            font11.setPointSize(12)
            self.prof_reqd_combo = CheckableComboBox(self.prof_reqd_frame)
            self.prof_reqd_combo.setObjectName(u"prof_reqd_combo")
            self.prof_reqd_combo.setFont(font11)
            self.horizontalLayout_23.addWidget(self.prof_reqd_combo)
            self.prof_reqd_combo.setStyleSheet(u"background-color: rgb(255, 255, 255);;\n"
                                                    "border-style: outset;\n"
                                                    "border-width: 1px;\n"
                                                    "border-radius:2px;\n"
                                                    "border-color: black;\n"
                                                    "padding: 4px;\n"
                                                    "")

            self.prof_reqd_combo_edit_page = CheckableComboBox(self.prof_reqd_frame_edit)
            self.prof_reqd_combo_edit_page.setObjectName(u"prof_reqd_combo_edit_page")
            self.prof_reqd_combo_edit_page.setFont(font11)
            self.horizontalLayout_72.addWidget(self.prof_reqd_combo_edit_page)
            self.prof_reqd_combo_edit_page.setStyleSheet(u"background-color: rgb(255, 255, 255);;\n"
                                                    "border-style: outset;\n"
                                                    "border-width: 1px;\n"
                                                    "border-radius:2px;\n"
                                                    "border-color: black;\n"
                                                    "padding: 4px;\n"
                                                    "")

            self.CHANGED = True
            
            
            self.therapist_view_horizontal_spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
            self.gridLayout.addItem(self.therapist_view_horizontal_spacer, 0, 50, 1, 1)

            self.patient_view_horizontal_spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
            self.gridLayout_2.addItem(self.patient_view_horizontal_spacer, 0, 50, 1, 1)

            self.ther_plan_verticalSpacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            self.gridLayout_3.addItem(self.ther_plan_verticalSpacer, 50, 0, 1, 1)

            self.ther_plan_horizontalSpacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
            self.gridLayout_3.addItem(self.ther_plan_horizontalSpacer, 0, 50, 1, 1)

            self.pnt_plan_verticalSpacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            self.gridLayout_4.addItem(self.ther_plan_verticalSpacer, 50, 0, 1, 1)

            self.pnt_plan_horizontalSpacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
            self.gridLayout_4.addItem(self.ther_plan_horizontalSpacer, 0, 50, 1, 1)


            self.db_connection = mc.connect(host=self.MYSQL_HOST, user=self.MYSQL_USER,
                    password=self.MYSQL_PASSWORD, database=self.MYSQL_DB)

            self.db_cursor = self.db_connection.cursor()

            self.dropdown_hidden  = False
            self.chevron_right = QtGui.QPixmap("./Icon/chevron-right.svg")
            self.chevron_down = QtGui.QPixmap("./Icon/chevron-down.svg")

            

            self.job_table_header = self.jobs_table.horizontalHeader()
            self.job_table_header.setSectionResizeMode(0,QtWidgets.QHeaderView.Stretch)
            self.job_table_header.setSectionResizeMode(1,QtWidgets.QHeaderView.Stretch)
            self.job_table_header.setSectionResizeMode(2,QtWidgets.QHeaderView.Stretch)
            self.jobs_table.verticalHeader().setVisible(False)
            self.jobs_table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
            self.jobs_table.setFocusPolicy(QtCore.Qt.NoFocus)
            self.jobs_table.setSelectionMode(QtWidgets.QTableWidget.NoSelection)
        
            self.jobs_table.setFont(QtGui.QFont("MS UI Gothic",16))
            
            self.therapists_tab.currentChanged.connect(self.on_thrapist_tab_change)
            self.patient_view_tab.currentChanged.connect(self.on_patient_tab_change)
            self.schedule_tab.currentChanged.connect(self.on_schedule_tab_change)
            self.ther_plan_tabs.currentChanged.connect(self.on_ther_plan_day_tab_change)
            self.pnt_plan_tabs.currentChanged.connect(self.on_pnt_plan_day_tab_change)


            if  self.dropdown_hidden:
                self.dropdown_menu.setMaximumHeight(0)
                self.add_icon_label.setPixmap(self.chevron_right)
            
            clickable(self.dashboard_opt).connect(self.on_click_dash)
            clickable(self.add_details_opt).connect(self.on_click_addItem)
            clickable(self.job_details).connect(self.add_job_det)
            clickable(self.patient_detail).connect(self.add_patient_det)
            clickable(self.therapist_details).connect(self.add_therapist_det)
            clickable(self.setting_opt).connect(self.on_click_settings)
            clickable(self.about_opt).connect(self.on_click_about)
                    
    
            self.job_add_button.clicked.connect(self.job_add_click)
            self.back_add_button.clicked.connect(self.change_job_stackindex)
            self.job_edit_save_button.clicked.connect(self.job_edit_save_click)
            self.add_therapist_button.clicked.connect(self.add_therapist_button_click)
            self.add_patient_button.clicked.connect(self.add_patient_button_click)
            self.ther_view_back_button.clicked.connect(self.back_ther_view_page_button_click)
            self.pnt_view_back_button.clicked.connect(self.back_pnt_view_page_button_click)
            self.back_add_button_edit.clicked.connect(self.ther_edit_back_click)
            self.edit_therapist_save_button.clicked.connect(self.on_click_edit_therapist_save_button)
            self.edit_patient_save_button.clicked.connect(self.on_click_edit_patient_save_button)
            self.back_add_button_edit_patient.clicked.connect(self.on_click_back_add_button_edit_patient)

            self.on_click_dash()


    def select_option(self,opt):
        self.options_chosen[opt][1] = True
        for item in self.options_chosen:
            chosen = item[1]
            optwid = item[0]
            if chosen:
                if opt==self.options_chosen.index(item):
                    optwid.setStyleSheet("QFrame{\n	background-color: rgb(238, 253, 208)\n	\n}")
                else:
                    item[1]=False
                    optwid.setStyleSheet("QFrame\n{\n	background-color: transparent;\n}\nQFrame:hover\n{	\n	background-color: rgb(71, 108, 150)\n\n}")
            else:
                optwid.setStyleSheet("QFrame\n{\n	background-color: transparent;\n}\nQFrame:hover\n{	\n	background-color: rgb(71, 108, 150)\n\n}")
        self.main_content.setCurrentIndex(opt)
    
    

    def on_click_dash(self):
        if self.CHANGED:
            self.MainAppStack.setCurrentIndex(1)
            algo_v2.find_schedule(self.MYSQL_HOST,self.MYSQL_USER,self.MYSQL_PASSWORD,self.MYSQL_DB)
            self.MainAppStack.setCurrentIndex(0)
            self.CHANGED=False

        if self.schedule_tab.currentIndex()==0:
            self.on_schedule_tab_change(0)
        else:
            self.on_schedule_tab_change(1)
        
            
        self.select_option(0)
            
    def on_click_addItem(self):

        if self.dropdown_hidden:
            self.dropdown_menu.setMaximumHeight(16777215)
            self.add_icon_label.setPixmap(self.chevron_down)
            self.dropdown_hidden = False
        else:
            self.dropdown_menu.setMaximumHeight(0)
            self.add_icon_label.setPixmap(self.chevron_right)
            self.dropdown_hidden = True



        # self.animation.start()
        # self.dropdown_menu.hide()

    def add_job_det(self):
        self.select_option(1)
        self.read_jobsFromDb()
        

    def add_therapist_det(self):
        self.therapist_prof_dropdown.clear()
        self.read_therapistFromDb()
        temp_dat = self.read_jobsFromDb()
        for job_tuple in temp_dat:
            self.therapist_prof_dropdown.addItem(job_tuple[1])
        if self.therapists_tab.currentIndex()==1:
            self.on_thrapist_tab_change(1)
        self.select_option(2)

    def add_patient_det(self):
        self.prof_reqd_combo.clear()
        self.read_patientsFromdb()
        
        temp_dat = self.read_jobsFromDb()
        job_list = []
        for job_tuple in temp_dat:
            job_list.append(job_tuple[1])
        self.prof_reqd_combo.addItems(job_list)
        self.prof_reqd_combo.setCurrentIndex(-1)
        if self.patient_view_tab.currentIndex():
            self.on_patient_tab_change(1)
        self.select_option(3)
    
    def on_click_settings(self):
        self.select_option(4)

    def on_click_about(self):
        self.select_option(5)

    def read_jobsFromDb(self):
        self.jobs_table.setRowCount(0)
        self.row=0
        self.db_cursor.execute("SELECT * FROM job_ids")
        
        self.job_id_data = self.db_cursor.fetchall()
        self.job_id = len(self.job_id_data)+1

        for job_id_row in self.job_id_data:
            self.create_job_row(job_id_row[0],job_id_row[1])

        return self.job_id_data
        

    def create_therapist_profile(self,ther_id,therapist_name,job_name,ther_address,avail_days,avail_time):
        therapist_template = QtWidgets.QFrame(self.therapist_view_main_frame)
        therapist_template.setObjectName(u"therapist_template")
        therapist_template.setMinimumSize(QtCore.QSize(333, 320))
        therapist_template.setMaximumSize(QtCore.QSize(333, 16777215))
        therapist_template.setStyleSheet(u"background-color: rgb(255, 255, 255);\n"
"border-style: outset;\n"
"border-width: px;\n"
"border-radius: 20px;\n"
"border-color: black;\n"
"padding: 4px;\n"
"\n"
"")
        therapist_template.setFrameShape(QtWidgets.QFrame.StyledPanel)
        therapist_template.setFrameShadow(QtWidgets.QFrame.Raised)
        therapist_template.setLineWidth(1)
        verticalLayout_19 = QtWidgets.QVBoxLayout(therapist_template)
        verticalLayout_19.setObjectName(u"verticalLayout_19")
        therapist_top_frame = QtWidgets.QFrame(therapist_template)
        therapist_top_frame.setObjectName(u"therapist_top_frame")
        therapist_top_frame.setMaximumSize(QtCore.QSize(16777215, 50))
        therapist_top_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        therapist_top_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_35 = QtWidgets.QHBoxLayout(therapist_top_frame)
        horizontalLayout_35.setSpacing(0)
        horizontalLayout_35.setObjectName(u"horizontalLayout_35")
        horizontalLayout_35.setContentsMargins(0, 0, 0, 0)
        therapist_delete_button = QtWidgets.QPushButton(therapist_top_frame)
        therapist_delete_button.setObjectName(u"therapist_delete_button")
        icon1 = QtGui.QIcon()
        icon1.addFile(u"Icon/x-circle.svg", QtCore.QSize(), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        therapist_delete_button.setIcon(icon1)
        therapist_delete_button.setIconSize(QtCore.QSize(30, 30))
        therapist_delete_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        therapist_delete_button.clicked.connect(lambda:self.on_ther_delete_click(ther_id))

        horizontalLayout_35.addWidget(therapist_delete_button)

        horizontalSpacer_8 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)

        horizontalLayout_35.addItem(horizontalSpacer_8)

        therapist_edit_button = QtWidgets.QPushButton(therapist_top_frame)
        therapist_edit_button.setObjectName(u"therapist_edit_button")
        icon2 = QtGui.QIcon()
        icon2.addFile(u"Icon/edit-2.svg", QtCore.QSize(), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        therapist_edit_button.setIcon(icon2)
        therapist_edit_button.setIconSize(QtCore.QSize(30, 30))
        therapist_edit_button.clicked.connect(lambda:self.on_ther_edit_click(ther_id,therapist_name,job_name,ther_address,avail_days,avail_time))
        therapist_edit_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        horizontalLayout_35.addWidget(therapist_edit_button)


        verticalLayout_19.addWidget(therapist_top_frame)

        therapist_image_icon = QtWidgets.QLabel(therapist_template)
        therapist_image_icon.setObjectName(u"therapist_image_icon")
        therapist_image_icon.setPixmap(QtGui.QPixmap(u"Icon/user.svg"))
        therapist_image_icon.setAlignment(QtCore.Qt.AlignCenter)

        verticalLayout_19.addWidget(therapist_image_icon)

        therapist_name_label_2 = QtWidgets.QLabel(therapist_template)
        therapist_name_label_2.setObjectName(u"therapist_name_label_2")
        font15 = QtGui.QFont()
        font15.setFamily(u"Century Gothic")
        font15.setPointSize(20)
        font15.setBold(True)
        font15.setWeight(75)
        therapist_name_label_2.setFont(font15)
        therapist_name_label_2.setStyleSheet(u"color:rgb(54, 53, 55)")
        therapist_name_label_2.setAlignment(QtCore.Qt.AlignCenter)
        therapist_name_label_2.setText(therapist_name)

        verticalLayout_19.addWidget(therapist_name_label_2)

        ther_job_frame = QtWidgets.QFrame(therapist_template)
        ther_job_frame.setObjectName(u"ther_job_frame")
        ther_job_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_job_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_22 = QtWidgets.QHBoxLayout(ther_job_frame)
        horizontalLayout_22.setObjectName(u"horizontalLayout_22")
        horizontalLayout_22.setContentsMargins(11, 0, 0, 0)
        ther_job_icon = QtWidgets.QLabel(ther_job_frame)
        ther_job_icon.setObjectName(u"ther_job_icon")
        ther_job_icon.setMaximumSize(QtCore.QSize(40, 40))
        ther_job_icon.setPixmap(QtGui.QPixmap(u"Icon/briefcase.svg"))
        ther_job_icon.setScaledContents(True)

        horizontalLayout_22.addWidget(ther_job_icon)

        ther_job_name_label = QtWidgets.QLabel(ther_job_frame)
        ther_job_name_label.setObjectName(u"ther_job_name_label")
        font16 = QtGui.QFont()
        font16.setFamily(u"MS UI Gothic")
        font16.setPointSize(18)
        font16.setUnderline(False)
        ther_job_name_label.setFont(font16)
        ther_job_name_label.setStyleSheet(u"color:rgb(54, 53, 55)")
        ther_job_name_label.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        ther_job_name_label.setText(job_name)

        horizontalLayout_22.addWidget(ther_job_name_label)


        verticalLayout_19.addWidget(ther_job_frame)

        ther_address_frame = QtWidgets.QFrame(therapist_template)
        ther_address_frame.setObjectName(u"ther_address_frame")
        ther_address_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_address_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_23 = QtWidgets.QHBoxLayout(ther_address_frame)
        horizontalLayout_23.setObjectName(u"horizontalLayout_23")
        horizontalLayout_23.setContentsMargins(11, 0, 0, 0)
        ther_home_icon_label = QtWidgets.QLabel(ther_address_frame)
        ther_home_icon_label.setObjectName(u"ther_home_icon_label")
        ther_home_icon_label.setMinimumSize(QtCore.QSize(0, 0))
        ther_home_icon_label.setMaximumSize(QtCore.QSize(40, 40))
        ther_home_icon_label.setPixmap(QtGui.QPixmap(u"Icon/home.svg"))
        ther_home_icon_label.setScaledContents(True)

        horizontalLayout_23.addWidget(ther_home_icon_label)

        ther_address_label = QtWidgets.QLabel(ther_address_frame)
        ther_address_label.setObjectName(u"ther_address_label")
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(ther_address_label.sizePolicy().hasHeightForWidth())
        ther_address_label.setSizePolicy(sizePolicy)
        font17 = QtGui.QFont()
        font17.setFamily(u"MS UI Gothic")
        font17.setPointSize(16)
        ther_address_label.setFont(font17)
        ther_address_label.setStyleSheet(u"color:rgb(54, 53, 55)")
        ther_address_label.setAlignment(QtCore.Qt.AlignLeft)
        ther_address_label.setWordWrap(True)
        ther_address_label.setText(ther_address)

        horizontalLayout_23.addWidget(ther_address_label)


        verticalLayout_19.addWidget(ther_address_frame)

        ther_days_frame = QtWidgets.QFrame(therapist_template)
        ther_days_frame.setObjectName(u"ther_days_frame")
        ther_days_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_days_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_24 = QtWidgets.QHBoxLayout(ther_days_frame)
        horizontalLayout_24.setObjectName(u"horizontalLayout_24")
        horizontalLayout_24.setContentsMargins(11, 0, 0, 0)
        thercal_icon_label = QtWidgets.QLabel(ther_days_frame)
        thercal_icon_label.setObjectName(u"thercal_icon_label")
        thercal_icon_label.setMaximumSize(QtCore.QSize(40, 40))
        thercal_icon_label.setPixmap(QtGui.QPixmap(u"Icon/calendar.svg"))
        thercal_icon_label.setScaledContents(True)

        horizontalLayout_24.addWidget(thercal_icon_label)

        ther_avail_days_label = QtWidgets.QLabel(ther_days_frame)
        ther_avail_days_label.setObjectName(u"ther_avail_days_label")
        font18 = QtGui.QFont()
        font18.setFamily(u"Bahnschrift SemiLight Condensed")
        font18.setPointSize(18)
        font18.setBold(False)
        font18.setWeight(50)
        ther_avail_days_label.setFont(font18)
        ther_avail_days_label.setStyleSheet(u"color:rgb(54, 53, 55)")
        ther_avail_days_label.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        ther_avail_days_label.setText(avail_days)
        horizontalLayout_24.addWidget(ther_avail_days_label)


        verticalLayout_19.addWidget(ther_days_frame)

        ther_avail_time_frame = QtWidgets.QFrame(therapist_template)
        ther_avail_time_frame.setObjectName(u"ther_avail_time_frame")
        ther_avail_time_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_avail_time_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_25 = QtWidgets.QHBoxLayout(ther_avail_time_frame)
        horizontalLayout_25.setObjectName(u"horizontalLayout_25")
        horizontalLayout_25.setContentsMargins(11, 0, 0, 0)
        ther_time_icon_label = QtWidgets.QLabel(ther_avail_time_frame)
        ther_time_icon_label.setObjectName(u"ther_time_icon_label")
        ther_time_icon_label.setMaximumSize(QtCore.QSize(40, 40))
        ther_time_icon_label.setPixmap(QtGui.QPixmap(u"Icon/clock.svg"))
        ther_time_icon_label.setScaledContents(True)

        horizontalLayout_25.addWidget(ther_time_icon_label)

        ther_avail_time_label = QtWidgets.QLabel(ther_avail_time_frame)
        ther_avail_time_label.setObjectName(u"ther_avail_time_label")
        font19 = QtGui.QFont()
        font19.setFamily(u"Bahnschrift SemiCondensed")
        font19.setPointSize(16)
        font19.setBold(False)
        font19.setWeight(50)
        ther_avail_time_label.setFont(font19)
        ther_avail_time_label.setStyleSheet(u"color:rgb(54, 53, 55)")
        ther_avail_time_label.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        ther_avail_time_label.setText(avail_time)

        horizontalLayout_25.addWidget(ther_avail_time_label)


        verticalLayout_19.addWidget(ther_avail_time_frame)

    
        return therapist_template

        
    def create_patient_profile(self,pnt_id,pat_name,pat_address,pat_profs,pat_avail_days):

        patient_template = QtWidgets.QFrame(self.therapist_view_main_frame_patient)
        patient_template.setObjectName(u"patient_template")
        patient_template.setMinimumSize(QtCore.QSize(380, 320))
        patient_template.setMaximumSize(QtCore.QSize(380, 16777215))
        patient_template.setStyleSheet(u"background-color: rgb(255, 255, 255);\n"
"border-style: outset;\n"
"border-width: px;\n"
"border-radius: 20px;\n"
"border-color: black;\n"
"padding: 4px;\n"
"\n"
"")
        patient_template.setFrameShape(QtWidgets.QFrame.StyledPanel)
        patient_template.setFrameShadow(QtWidgets.QFrame.Raised)
        patient_template.setLineWidth(1)
        verticalLayout_25 = QtWidgets.QVBoxLayout(patient_template)
        verticalLayout_25.setSpacing(24)
        verticalLayout_25.setObjectName(u"verticalLayout_25")
        verticalLayout_25.setContentsMargins(11, 10, -1, -1)
        patient_top_frame = QtWidgets.QFrame(patient_template)
        patient_top_frame.setObjectName(u"patient_top_frame")
        patient_top_frame.setMaximumSize(QtCore.QSize(16777215, 50))
        patient_top_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        patient_top_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_29 = QtWidgets.QHBoxLayout(patient_top_frame)
        horizontalLayout_29.setSpacing(0)
        horizontalLayout_29.setObjectName(u"horizontalLayout_29")
        horizontalLayout_29.setContentsMargins(0, 0, 0, 0)
        patient_delete_button = QtWidgets.QPushButton(patient_top_frame)
        patient_delete_button.setObjectName(u"patient_delete_button")
        icon1 = QtGui.QIcon()
        icon1.addFile(u"Icon/x-circle.svg", QtCore.QSize(), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        patient_delete_button.setIcon(icon1)
        patient_delete_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        patient_delete_button.setIconSize(QtCore.QSize(30, 30))
        patient_delete_button.clicked.connect(lambda:self.on_patient_delete_click(pnt_id))

        horizontalLayout_29.addWidget(patient_delete_button)

        horizontalSpacer_7 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)

        horizontalLayout_29.addItem(horizontalSpacer_7)

        patient_edit_button = QtWidgets.QPushButton(patient_top_frame)
        patient_edit_button.setObjectName(u"patient_edit_button")
        icon2 = QtGui.QIcon()
        icon2.addFile(u"Icon/edit-2.svg",QtCore.QSize(), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        patient_edit_button.setIcon(icon2)
        patient_edit_button.setIconSize(QtCore.QSize(30, 30))
        patient_edit_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        patient_edit_button.clicked.connect(lambda:self.on_patient_edit_click(pnt_id,pat_name,pat_address,pat_profs,pat_avail_days))

        horizontalLayout_29.addWidget(patient_edit_button)


        verticalLayout_25.addWidget(patient_top_frame)

        patient_image_icon = QtWidgets.QLabel(patient_template)
        patient_image_icon.setObjectName(u"patient_image_icon")
        patient_image_icon.setPixmap(QtGui.QPixmap(u"Icon/user.svg"))
        patient_image_icon.setAlignment(QtCore.Qt.AlignCenter)

        verticalLayout_25.addWidget(patient_image_icon)

        patient_name_label = QtWidgets.QLabel(patient_template)
        patient_name_label.setObjectName(u"patient_name_label")
        font17 = QtGui.QFont()
        font17.setFamily(u"Century Gothic")
        font17.setPointSize(20)
        font17.setBold(True)
        font17.setWeight(75)
        patient_name_label.setFont(font17)
        patient_name_label.setStyleSheet(u"color:rgb(54, 53, 55)")
        patient_name_label.setAlignment(QtCore.Qt.AlignCenter)
        patient_name_label.setText(pat_name)

        verticalLayout_25.addWidget(patient_name_label)
    

        patient_address_frame = QtWidgets.QFrame(patient_template)
        patient_address_frame.setObjectName(u"patient_address_frame")
        patient_address_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        patient_address_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_33 = QtWidgets.QHBoxLayout(patient_address_frame)
        horizontalLayout_33.setObjectName(u"horizontalLayout_33")
        horizontalLayout_33.setContentsMargins(11, 0, 0, 0)
        patient_home_icon_label = QtWidgets.QLabel(patient_address_frame)
        patient_home_icon_label.setObjectName(u"patient_home_icon_label")
        patient_home_icon_label.setMinimumSize(QtCore.QSize(0, 0))
        patient_home_icon_label.setMaximumSize(QtCore.QSize(40, 40))
        patient_home_icon_label.setPixmap(QtGui.QPixmap(u"Icon/home.svg"))
        patient_home_icon_label.setScaledContents(True)

        horizontalLayout_33.addWidget(patient_home_icon_label)

        patient_address_label = QtWidgets.QLabel(patient_address_frame)
        patient_address_label.setObjectName(u"patient_address_label")
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(patient_address_label.sizePolicy().hasHeightForWidth())
        patient_address_label.setSizePolicy(sizePolicy)
        font18 = QtGui.QFont()
        font18.setFamily(u"MS UI Gothic")
        font18.setPointSize(16)
        patient_address_label.setFont(font18)
        patient_address_label.setStyleSheet(u"color:rgb(54, 53, 55)")
        patient_address_label.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        patient_address_label.setWordWrap(True)
        patient_address_label.setText(pat_address)
        horizontalLayout_33.addWidget(patient_address_label)


        verticalLayout_25.addWidget(patient_address_frame)

        patient_job_frame = QtWidgets.QFrame(patient_template)
        patient_job_frame.setObjectName(u"patient_job_frame")
        patient_job_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        patient_job_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_32 = QtWidgets.QHBoxLayout(patient_job_frame)
        horizontalLayout_32.setObjectName(u"horizontalLayout_32")
        horizontalLayout_32.setContentsMargins(11, 0, 0, 0)
        patient_job_icon = QtWidgets.QLabel(patient_job_frame)
        patient_job_icon.setObjectName(u"patient_job_icon")
        patient_job_icon.setMaximumSize(QtCore.QSize(40, 40))
        patient_job_icon.setPixmap(QtGui.QPixmap(u"Icon/briefcase.svg"))
        patient_job_icon.setScaledContents(True)

        horizontalLayout_32.addWidget(patient_job_icon)

        pat_reqd_job_name_label = QtWidgets.QLabel(patient_job_frame)
        pat_reqd_job_name_label.setObjectName(u"pat_reqd_job_name_label")
        font19 = QtGui.QFont()
        font19.setFamily(u"MS UI Gothic")
        font19.setPointSize(18)
        font19.setUnderline(False)
        pat_reqd_job_name_label.setFont(font19)
        pat_reqd_job_name_label.setStyleSheet(u"color:rgb(54, 53, 55)")
        pat_reqd_job_name_label.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        pat_reqd_job_name_label.setText(pat_profs)
        horizontalLayout_32.addWidget(pat_reqd_job_name_label)


        verticalLayout_25.addWidget(patient_job_frame)

        patient_days_frame = QtWidgets.QFrame(patient_template)
        patient_days_frame.setObjectName(u"patient_days_frame")
        patient_days_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        patient_days_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_34 = QtWidgets.QHBoxLayout(patient_days_frame)
        horizontalLayout_34.setObjectName(u"horizontalLayout_34")
        horizontalLayout_34.setContentsMargins(11, 0, 0, 0)
        patient_icon_label_2 = QtWidgets.QLabel(patient_days_frame)
        patient_icon_label_2.setObjectName(u"patient_icon_label_2")
        patient_icon_label_2.setMaximumSize(QtCore.QSize(40, 40))
        patient_icon_label_2.setPixmap(QtGui.QPixmap(u"Icon/calendar.svg"))
        patient_icon_label_2.setScaledContents(True)

        horizontalLayout_34.addWidget(patient_icon_label_2)

        patient_avail_days_label = QtWidgets.QLabel(patient_days_frame)
        patient_avail_days_label.setObjectName(u"patient_avail_days_label")
        font20 = QtGui.QFont()
        font20.setFamily(u"Bahnschrift SemiLight Condensed")
        font20.setPointSize(18)
        font20.setBold(False)
        font20.setWeight(50)
        patient_avail_days_label.setFont(font20)
        patient_avail_days_label.setStyleSheet(u"color:rgb(54, 53, 55)")
        patient_avail_days_label.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        patient_avail_days_label.setText(pat_avail_days)
        horizontalLayout_34.addWidget(patient_avail_days_label)


        verticalLayout_25.addWidget(patient_days_frame)


        return patient_template

    def create_ther_plan_template(self,ther_id,name):
        
        ther_name_tempate = QtWidgets.QFrame(self.ther_plan_scroll_frame)
        ther_name_tempate.setObjectName(u"ther_name_tempate")
        ther_name_tempate.setMinimumSize(QtCore.QSize(0, 0))
        ther_name_tempate.setStyleSheet(u"background-color: rgb(255, 255, 255);\n"
"border-style: outset;\n"
"border-width: px;\n"
"border-radius: 20px;\n"
"border-color: black;\n"
"padding: 4px;\n"
"\n"
"")
        ther_name_tempate.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_name_tempate.setFrameShadow(QtWidgets.QFrame.Raised)
        verticalLayout_25 = QtWidgets.QVBoxLayout(ther_name_tempate)
        verticalLayout_25.setSpacing(19)
        verticalLayout_25.setObjectName(u"verticalLayout_25")
        verticalLayout_25.setContentsMargins(30, 25, 30, 21)
        ther_icon_frame = QtWidgets.QFrame(ther_name_tempate)
        ther_icon_frame.setObjectName(u"ther_icon_frame")
        ther_icon_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_icon_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_29 = QtWidgets.QHBoxLayout(ther_icon_frame)
        horizontalLayout_29.setSpacing(0)
        horizontalLayout_29.setObjectName(u"horizontalLayout_29")
        horizontalLayout_29.setContentsMargins(0, 0, 0, 0)
        ther_det_icon_label = QtWidgets.QLabel(ther_icon_frame)
        ther_det_icon_label.setObjectName(u"ther_det_icon_label")
        ther_det_icon_label.setMaximumSize(QtCore.QSize(60, 60))
        ther_det_icon_label.setPixmap(QtGui.QPixmap(u"Icon/therapist.png"))
        ther_det_icon_label.setScaledContents(True)
        ther_det_icon_label.setAlignment(QtCore.Qt.AlignCenter)

        horizontalLayout_29.addWidget(ther_det_icon_label)


        verticalLayout_25.addWidget(ther_icon_frame)

        ther_view_name_label = QtWidgets.QLabel(ther_name_tempate)
        ther_view_name_label.setObjectName(u"ther_view_name_label")
        font4 = QtGui.QFont()
        font4.setFamily(u"Tw Cen MT")
        font4.setPointSize(18)
        ther_view_name_label.setFont(font4)
        ther_view_name_label.setAlignment(QtCore.Qt.AlignCenter)
        ther_view_name_label.setMinimumSize(QtCore.QSize(230, 0))
        ther_view_name_label.setMaximumSize(QtCore.QSize(230, 16777215))
        ther_view_name_label.setText(name)

        verticalLayout_25.addWidget(ther_view_name_label)

        view_plan_button = QtWidgets.QPushButton(ther_name_tempate)
        view_plan_button.setObjectName(u"view_plan_button")
        font5 = QtGui.QFont()
        font5.setFamily(u"Segoe UI Semibold")
        font5.setPointSize(12)
        font5.setBold(True)
        font5.setWeight(75)
        view_plan_button.setFont(font5)
        view_plan_button.setText("View Plan")
        view_plan_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        view_plan_button.clicked.connect(lambda:self.view_plan_button_click(ther_id))
        view_plan_button.setStyleSheet(u"QPushButton{\nbackground-color: rgb(255, 153, 69);\n"
"border-style: outset;\n"
"border-width: 1px;\n"
"border-radius: 10px;\n"
"border-color: black;\n"
"padding: 4px;\n}\n"
"QPushButton:hover{\nbackground-color: rgb(229, 137, 62)\n}")

        verticalLayout_25.addWidget(view_plan_button)

        return ther_name_tempate

    def create_pnt_plan_template(self,pnt_id,name):
        pnt_name_tempate = QtWidgets.QFrame(self.pnt_plan_scroll_frame)
        pnt_name_tempate.setObjectName(u"pnt_name_tempate")
        pnt_name_tempate.setMinimumSize(QtCore.QSize(0, 0))
        pnt_name_tempate.setStyleSheet(u"background-color: rgb(255, 255, 255);\n"
"border-style: outset;\n"
"border-width: px;\n"
"border-radius: 20px;\n"
"border-color: black;\n"
"padding: 4px;\n"
"\n"
"")
        pnt_name_tempate.setFrameShape(QtWidgets.QFrame.StyledPanel)
        pnt_name_tempate.setFrameShadow(QtWidgets.QFrame.Raised)
        verticalLayout_25 = QtWidgets.QVBoxLayout(pnt_name_tempate)
        verticalLayout_25.setSpacing(19)
        
        verticalLayout_25.setContentsMargins(30, 25, 30, 21)
        pnt_icon_frame = QtWidgets.QFrame(pnt_name_tempate)
        pnt_icon_frame.setObjectName(u"pnt_icon_frame")
        pnt_icon_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        pnt_icon_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_29 = QtWidgets.QHBoxLayout(pnt_icon_frame)
        horizontalLayout_29.setSpacing(0)
        
        horizontalLayout_29.setContentsMargins(0, 0, 0, 0)
        pnt_det_icon_label = QtWidgets.QLabel(pnt_icon_frame)
        
        pnt_det_icon_label.setMaximumSize(QtCore.QSize(60, 60))
        pnt_det_icon_label.setPixmap(QtGui.QPixmap(u"Icon/user_circle.png"))
        pnt_det_icon_label.setScaledContents(True)
        pnt_det_icon_label.setAlignment(QtCore.Qt.AlignCenter)

        horizontalLayout_29.addWidget(pnt_det_icon_label)


        verticalLayout_25.addWidget(pnt_icon_frame)

        pnt_view_name_label = QtWidgets.QLabel(pnt_name_tempate)
        
        font4 = QtGui.QFont()
        font4.setFamily(u"Tw Cen MT")
        font4.setPointSize(18)
        pnt_view_name_label.setFont(font4)
        pnt_view_name_label.setAlignment(QtCore.Qt.AlignCenter)
        pnt_view_name_label.setMinimumSize(QtCore.QSize(230, 0))
        pnt_view_name_label.setMaximumSize(QtCore.QSize(230, 16777215))
        pnt_view_name_label.setText(name)

        verticalLayout_25.addWidget(pnt_view_name_label)

        view_pnt_plan_button = QtWidgets.QPushButton(pnt_name_tempate)
        view_pnt_plan_button.setObjectName(u"view_pnt_plan_button")
        font5 = QtGui.QFont()
        font5.setFamily(u"Segoe UI Semibold")
        font5.setPointSize(12)
        font5.setBold(True)
        font5.setWeight(75)
        view_pnt_plan_button.setFont(font5)
        view_pnt_plan_button.setText("View Plan")
        view_pnt_plan_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        view_pnt_plan_button.clicked.connect(lambda:self.view_pnt_plan_button_click(pnt_id))
        view_pnt_plan_button.setStyleSheet(u"QPushButton{\nbackground-color: rgb(188, 255, 184);\n"
"border-style: outset;\n"
"border-width: 1px;\n"
"border-radius: 10px;\n"
"border-color: black;\n"
"padding: 4px;\n}\n"
"QPushButton:hover{\nbackground-color: rgb(174, 236, 170)\n}")

        verticalLayout_25.addWidget(view_pnt_plan_button)

        return pnt_name_tempate


    def create_ther_plan_list(self,parent_frame,pnt_no,pnt_name,pnt_address):

        ther_plan_template = QtWidgets.QFrame(parent_frame)
    
        ther_plan_template.setStyleSheet(u"background-color: rgb(255, 248, 194)\n"
"\n"
"")
        ther_plan_template.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_plan_template.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_39 = QtWidgets.QHBoxLayout(ther_plan_template)
        horizontalLayout_39.setObjectName(u"horizontalLayout_39")
        pnt_no_frame = QtWidgets.QFrame(ther_plan_template)
        
        pnt_no_frame.setFrameShape(QtWidgets.QFrame.NoFrame)
        pnt_no_frame.setFrameShadow(QtWidgets.QFrame.Plain)
        pnt_no_frame.setLineWidth(0)
        horizontalLayout_40 = QtWidgets.QHBoxLayout(pnt_no_frame)
        horizontalLayout_40.setObjectName(u"horizontalLayout_40")
        pnt_no_label = QtWidgets.QLabel(pnt_no_frame)
        
        pnt_no_label.setMaximumSize(QtCore.QSize(50, 50))
        font6 = QtGui.QFont()
        font6.setFamily(u"Segoe MDL2 Assets")
        font6.setPointSize(16)
        pnt_no_label.setFont(font6)
        pnt_no_label.setStyleSheet(u"background-color: rgb(255, 251, 199);\n"
"border-style: outset;\n"
"border-width: 1px;\n"
"border-radius: 10px;\n"
"border-color: black;\n"
"padding: 4px;\n"
"")
        pnt_no_label.setAlignment(QtCore.Qt.AlignCenter)
        pnt_no_label.setText(pnt_no)

        horizontalLayout_40.addWidget(pnt_no_label)


        horizontalLayout_39.addWidget(pnt_no_frame)

        sch_pnt_detail_frame = QtWidgets.QFrame(ther_plan_template)
        
        sch_pnt_detail_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        sch_pnt_detail_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        verticalLayout_32 = QtWidgets.QVBoxLayout(sch_pnt_detail_frame)
        
        pnt_name_icon_frame = QtWidgets.QFrame(sch_pnt_detail_frame)
       
        pnt_name_icon_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        pnt_name_icon_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_42 = QtWidgets.QHBoxLayout(pnt_name_icon_frame)
        
        plan_pnt_icon = QtWidgets.QLabel(pnt_name_icon_frame)
        plan_pnt_icon.setObjectName(u"plan_pnt_icon")
        plan_pnt_icon.setMaximumSize(QtCore.QSize(40, 40))
        plan_pnt_icon.setPixmap(QtGui.QPixmap(u"Icon/user_circle.png"))
        plan_pnt_icon.setScaledContents(True)

        horizontalLayout_42.addWidget(plan_pnt_icon)

        plan_pnt_name = QtWidgets.QLabel(pnt_name_icon_frame)
        
        font7 = QtGui.QFont()
        font7.setFamily(u"Tw Cen MT")
        font7.setPointSize(20)
        plan_pnt_name.setFont(font7)
        plan_pnt_name.setText(pnt_name)

        horizontalLayout_42.addWidget(plan_pnt_name)

        horizontalLayout_42.setStretch(1, 10)

        verticalLayout_32.addWidget(pnt_name_icon_frame)

        plan_pnt_addr_icon_frame = QtWidgets.QFrame(sch_pnt_detail_frame)
        
        plan_pnt_addr_icon_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        plan_pnt_addr_icon_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_41 = QtWidgets.QHBoxLayout(plan_pnt_addr_icon_frame)
        
        pnt_home_icon = QtWidgets.QLabel(plan_pnt_addr_icon_frame)
        
        pnt_home_icon.setMaximumSize(QtCore.QSize(40, 40))
        pnt_home_icon.setPixmap(QtGui.QPixmap(u"Icon/home.svg"))
        pnt_home_icon.setScaledContents(True)

        horizontalLayout_41.addWidget(pnt_home_icon)

        pnt_addr_label = QtWidgets.QLabel(plan_pnt_addr_icon_frame)
        
        font8 = QtGui.QFont()
        font8.setFamily(u"Tw Cen MT")
        font8.setPointSize(18)
        pnt_addr_label.setFont(font8)
        pnt_addr_label.setTextFormat(QtCore.Qt.AutoText)
        pnt_addr_label.setMargin(10)
        pnt_addr_label.setText(pnt_address)

        horizontalLayout_41.addWidget(pnt_addr_label)

        horizontalLayout_41.setStretch(1, 10)

        verticalLayout_32.addWidget(plan_pnt_addr_icon_frame)


        horizontalLayout_39.addWidget(sch_pnt_detail_frame)

        horizontalLayout_39.setStretch(0, 1)
        horizontalLayout_39.setStretch(1, 10)

        return ther_plan_template

    def create_pnt_plan_list(self,parent_frame,ther_name,ther_prof,apnt_time):

        pnt_plan_template = QtWidgets.QFrame(parent_frame)
        pnt_plan_template.setObjectName(u"pnt_plan_template")
        pnt_plan_template.setStyleSheet(u"background-color: rgb(228, 245, 255)")
        pnt_plan_template.setFrameShape(QtWidgets.QFrame.StyledPanel)
        pnt_plan_template.setFrameShadow(QtWidgets.QFrame.Raised)
        verticalLayout_50 = QtWidgets.QVBoxLayout(pnt_plan_template)
        verticalLayout_50.setSpacing(19)
        verticalLayout_50.setObjectName(u"verticalLayout_50")
        verticalLayout_50.setContentsMargins(-1, -1, -1, 26)
        appnt_time_frame = QtWidgets.QFrame(pnt_plan_template)
        appnt_time_frame.setObjectName(u"appnt_time_frame")
        appnt_time_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        appnt_time_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_57 = QtWidgets.QHBoxLayout(appnt_time_frame)
        horizontalLayout_57.setObjectName(u"horizontalLayout_57")
        appnt_time_label = QtWidgets.QLabel(appnt_time_frame)
        appnt_time_label.setObjectName(u"appnt_time_label")
        font6 = QtGui.QFont()
        font6.setFamily(u"Tw Cen MT")
        font6.setPointSize(22)
        font6.setBold(True)
        font6.setWeight(75)
        appnt_time_label.setFont(font6)
        appnt_time_label.setText(f"Appointment at {apnt_time}")

        horizontalLayout_57.addWidget(appnt_time_label)


        verticalLayout_50.addWidget(appnt_time_frame)

        ther_det_headingframe = QtWidgets.QFrame(pnt_plan_template)
        ther_det_headingframe.setObjectName(u"ther_det_headingframe")
        ther_det_headingframe.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_det_headingframe.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_58 = QtWidgets.QHBoxLayout(ther_det_headingframe)
        horizontalLayout_58.setObjectName(u"horizontalLayout_58")
        ther_det_head_label = QtWidgets.QLabel(ther_det_headingframe)
        ther_det_head_label.setObjectName(u"ther_det_head_label")
        font7 = QtGui.QFont()
        font7.setFamily(u"Segoe UI")
        font7.setPointSize(18)
        font7.setItalic(True)
        ther_det_head_label.setFont(font7)
        ther_det_head_label.setText("Therapist details:")

        horizontalLayout_58.addWidget(ther_det_head_label)


        verticalLayout_50.addWidget(ther_det_headingframe)

        ther_det_main_frame = QtWidgets.QFrame(pnt_plan_template)
        ther_det_main_frame.setObjectName(u"ther_det_main_frame")
        ther_det_main_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_det_main_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        verticalLayout_51 = QtWidgets.QVBoxLayout(ther_det_main_frame)
        verticalLayout_51.setSpacing(22)
        verticalLayout_51.setObjectName(u"verticalLayout_51")
        verticalLayout_51.setContentsMargins(0, 0, 0, 0)
        ther_name_det_frame = QtWidgets.QFrame(ther_det_main_frame)
        ther_name_det_frame.setObjectName(u"ther_name_det_frame")
        ther_name_det_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_name_det_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_59 = QtWidgets.QHBoxLayout(ther_name_det_frame)
        horizontalLayout_59.setSpacing(0)
        horizontalLayout_59.setObjectName(u"horizontalLayout_59")
        horizontalLayout_59.setContentsMargins(58, 0, 15, 0)
        ther_plan_icon_frame = QtWidgets.QFrame(ther_name_det_frame)
        ther_plan_icon_frame.setObjectName(u"ther_plan_icon_frame")
        ther_plan_icon_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_plan_icon_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_61 = QtWidgets.QHBoxLayout(ther_plan_icon_frame)
        horizontalLayout_61.setSpacing(0)
        horizontalLayout_61.setObjectName(u"horizontalLayout_61")
        horizontalLayout_61.setContentsMargins(0, 0, 0, 0)
        ther_icon_plan = QtWidgets.QLabel(ther_plan_icon_frame)
        ther_icon_plan.setObjectName(u"ther_icon_plan")
        ther_icon_plan.setMaximumSize(QtCore.QSize(55, 55))
        ther_icon_plan.setPixmap(QtGui.QPixmap(u"Icon/user.svg"))
        ther_icon_plan.setScaledContents(True)

        horizontalLayout_61.addWidget(ther_icon_plan)


        horizontalLayout_59.addWidget(ther_plan_icon_frame)

        ther_name_plan_frame = QtWidgets.QFrame(ther_name_det_frame)
        ther_name_plan_frame.setObjectName(u"ther_name_plan_frame")
        ther_name_plan_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_name_plan_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_63 = QtWidgets.QHBoxLayout(ther_name_plan_frame)
        horizontalLayout_63.setObjectName(u"horizontalLayout_63")
        ther_name_plan_label = QtWidgets.QLabel(ther_name_plan_frame)
        ther_name_plan_label.setObjectName(u"ther_name_plan_label")
        font8 = QtGui.QFont()
        font8.setFamily(u"Trebuchet MS")
        font8.setPointSize(20)
        font8.setBold(False)
        font8.setWeight(50)
        ther_name_plan_label.setFont(font8)
        ther_name_plan_label.setText(ther_name)
        horizontalLayout_63.addWidget(ther_name_plan_label)
        


        horizontalLayout_59.addWidget(ther_name_plan_frame)

        horizontalLayout_59.setStretch(0, 1)
        horizontalLayout_59.setStretch(1, 10)

        verticalLayout_51.addWidget(ther_name_det_frame)

        ther_prof_detail_frame = QtWidgets.QFrame(ther_det_main_frame)
        ther_prof_detail_frame.setObjectName(u"ther_prof_detail_frame")
        ther_prof_detail_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_prof_detail_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_60 = QtWidgets.QHBoxLayout(ther_prof_detail_frame)
        horizontalLayout_60.setSpacing(0)
        horizontalLayout_60.setObjectName(u"horizontalLayout_60")
        horizontalLayout_60.setContentsMargins(58, 0, 0, 0)
        ther_prof_plan_icon_frame = QtWidgets.QFrame(ther_prof_detail_frame)
        ther_prof_plan_icon_frame.setObjectName(u"ther_prof_plan_icon_frame")
        ther_prof_plan_icon_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_prof_plan_icon_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_62 = QtWidgets.QHBoxLayout(ther_prof_plan_icon_frame)
        horizontalLayout_62.setSpacing(0)
        horizontalLayout_62.setObjectName(u"horizontalLayout_62")
        horizontalLayout_62.setContentsMargins(0, 0, 0, 0)
        ther_plan_prof_icon_label = QtWidgets.QLabel(ther_prof_plan_icon_frame)
        ther_plan_prof_icon_label.setObjectName(u"ther_plan_prof_icon_label")
        ther_plan_prof_icon_label.setMaximumSize(QtCore.QSize(55, 55))
        ther_plan_prof_icon_label.setPixmap(QtGui.QPixmap(u"Icon/briefcase.svg"))
        ther_plan_prof_icon_label.setScaledContents(True)

        horizontalLayout_62.addWidget(ther_plan_prof_icon_label)


        horizontalLayout_60.addWidget(ther_prof_plan_icon_frame)

        ther_prof_plan_frame = QtWidgets.QFrame(ther_prof_detail_frame)
        ther_prof_plan_frame.setObjectName(u"ther_prof_plan_frame")
        ther_prof_plan_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        ther_prof_plan_frame.setFrameShadow(QtWidgets.QFrame.Raised)
        horizontalLayout_64 = QtWidgets.QHBoxLayout(ther_prof_plan_frame)
        horizontalLayout_64.setObjectName(u"horizontalLayout_64")
        ther_prof_name_label = QtWidgets.QLabel(ther_prof_plan_frame)
        ther_prof_name_label.setObjectName(u"ther_prof_name_label")
        font9 = QtGui.QFont()
        font9.setFamily(u"Trebuchet MS")
        font9.setPointSize(20)
        ther_prof_name_label.setFont(font9)
        ther_prof_name_label.setText(ther_prof)

        horizontalLayout_64.addWidget(ther_prof_name_label)


        horizontalLayout_60.addWidget(ther_prof_plan_frame)

        horizontalLayout_60.setStretch(0, 1)
        horizontalLayout_60.setStretch(1, 10)

        verticalLayout_51.addWidget(ther_prof_detail_frame)


        verticalLayout_50.addWidget(ther_det_main_frame)


        return pnt_plan_template
    
        

    def create_job_row(self,id,name):
        self.jobs_table.setRowCount(self.row+1)
        action_layout = QtWidgets.QHBoxLayout()


        job_edit_button = QtWidgets.QPushButton()
        job_edit_button.setIcon(QtGui.QIcon("./Icon/edit-2.svg"))
        job_edit_button.setStyleSheet("QPushButton{background-color: rgb(217, 234, 255);\nborder-style: outset;\nborder-width: 1px;\nborder-radius: 15px;\nborder-color: black;\npadding: 4px;}\nQPushButton:hover{background-color:rgb(201, 217, 236)}")
        job_edit_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        temp_row = self.row
        job_edit_button.clicked.connect(lambda:self.job_edit_click(temp_row))
        
        job_delete_button = QtWidgets.QPushButton()
        job_delete_button.setIcon(QtGui.QIcon("./Icon/x-circle.svg"))
        job_delete_button.setStyleSheet("QPushButton{\nbackground-color: rgb(217, 234, 255);\nborder-style: outset;\nborder-width: 1px;\nborder-radius: 15px;\nborder-color: black;\npadding: 4px;\n}\nQPushButton:hover{background-color:rgb(225, 69, 69)}")
        job_delete_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        job_delete_button.clicked.connect(lambda:self.job_delete_click(temp_row))

        action_layout.addWidget(job_edit_button)
        action_layout.addWidget(job_delete_button)

        action_frame = QtWidgets.QFrame(self.jobs_table)
        action_frame.setLayout(action_layout)

        job_id = QtWidgets.QTableWidgetItem()
        job_id.setText(id)
        job_id.setTextAlignment(QtCore.Qt.AlignCenter)

        job_name = QtWidgets.QTableWidgetItem()
        job_name.setText(name)
        job_name.setTextAlignment(QtCore.Qt.AlignVCenter)
    

        self.jobs_table.setItem(self.row, 0, job_id)
        self.jobs_table.setItem(self.row, 1, job_name)
        self.jobs_table.setCellWidget(self.row, 2, action_frame)

        self.jobs_table.resizeRowsToContents()
        self.row+=1

    def on_thrapist_tab_change(self,tab_index):
        
        
        ther_no = 0
        if tab_index==1:
            print("tabchanged")
            self.clear_layout(self.gridLayout)
            ther_data = self.read_therapistFromDb()
            self.db_cursor.execute("SELECT * FROM therapist_availability")
            ther_avail_data = self.db_cursor.fetchall()
            for row in ther_data:
                ther_name = row[1]
                ther_address =row[2]
                self.db_cursor.execute("SELECT name from job_ids WHERE ID = %s",(row[3],))
                ther_job = self.db_cursor.fetchall()[0][0]

                ther_avail_days = ther_avail_data[ther_data.index(row)][2].replace(","," ")
                ther_from = ther_avail_data[ther_data.index(row)][3]
                ther_to = ther_avail_data[ther_data.index(row)][4]

                ther_time_avail = ther_from + " - " + ther_to

                t1 = self.create_therapist_profile(row[0],ther_name,ther_job,ther_address,ther_avail_days,ther_time_avail)
                self.gridLayout.addWidget(t1, 0, ther_no, 1, 1)
                ther_no+=1

    def on_patient_tab_change(self,tab_index):
        
        p_no = 0
        if tab_index==1:
            self.clear_layout(self.gridLayout_2)

            patient_data = self.read_patientsFromdb()
            for row in patient_data:
                patient_name = row[1]
                patient_address = row[2]
                pat_avail_days = row[3].replace(","," ")
                self.db_cursor.execute("SELECT Required_Profession FROM therapy_plans WHERE ID = %s",(row[0],))
                reqd_prof_list = []
                for plan_row in self.db_cursor.fetchall():
                    for job_id in plan_row[0].split(","):
                        self.db_cursor.execute("SELECT name from job_ids WHERE ID=%s",(job_id,))
                        reqd_prof_list.append(self.db_cursor.fetchall()[0][0])
                reqd_prof_str = "\n".join(reqd_prof_list)
                p = self.create_patient_profile(row[0],patient_name,patient_address,reqd_prof_str,pat_avail_days)
                self.gridLayout_2.addWidget(p, 0, p_no, 1, 1)
                p_no+=1
                

    def on_schedule_tab_change(self,tab_index):
        template_row = 0
        template_col = 0
        if tab_index==0:
            self.db_cursor.execute("SELECT ID,Therapist FROM therapists")
            therapist_names = self.db_cursor.fetchall()
            for ther_name in therapist_names:
                plan_temp = self.create_ther_plan_template(ther_name[0],ther_name[1])
                self.gridLayout_3.addWidget(plan_temp, template_row, template_col, 1, 1)
                template_col+=1
                if template_col==4:
                    template_col=0
                    template_row+=1
        if tab_index==1:
            self.db_cursor.execute("SELECT ID,Patient FROM patients")
            pnt_names = self.db_cursor.fetchall()
            for pnt_name in pnt_names:
                pnt_temp = self.create_pnt_plan_template(pnt_name[0],pnt_name[1])
                self.gridLayout_4.addWidget(pnt_temp,template_row,template_col,1,1)
                template_col+=1
                if template_col==4:
                    template_col=0
                    template_row+=1


    def on_ther_plan_day_tab_change(self,tab_index):

        
        if tab_index==0:
            parent_frame = self.ther_sch_frame_mon
            v_layout = self.verticalLayout_31
            self.clear_layout(v_layout)
            if self.ther_schedule[0] !='' and self.ther_schedule[0] is not None:
                pnts_list = self.ther_schedule[0].split('-')
                self.ther_plan_list_maker(parent_frame,v_layout,pnts_list)
        elif tab_index==1:
            parent_frame = self.ther_sch_frame_tue
            v_layout = self.verticalLayout_36
            self.clear_layout(v_layout)
            if self.ther_schedule[1] !='' and self.ther_schedule[1] is not None:
                pnts_list = self.ther_schedule[1].split('-')
                self.ther_plan_list_maker(parent_frame,v_layout,pnts_list)
        elif tab_index==2:
            parent_frame = self.ther_sch_frame_wed
            v_layout = self.verticalLayout_37
            self.clear_layout(v_layout)
            if self.ther_schedule[2] !='' and self.ther_schedule[2] is not None:
                pnts_list = self.ther_schedule[2].split('-')
                self.ther_plan_list_maker(parent_frame,v_layout,pnts_list)
        elif tab_index==3:
            parent_frame = self.ther_sch_frame_thur
            v_layout = self.verticalLayout_38
            self.clear_layout(v_layout)
            if self.ther_schedule[3] !='' and self.ther_schedule[3] is not None:
                pnts_list = self.ther_schedule[3].split('-')
                self.ther_plan_list_maker(parent_frame,v_layout,pnts_list)
        elif tab_index==4:
            parent_frame = self.ther_sch_frame_fri
            v_layout = self.verticalLayout_39
            self.clear_layout(v_layout)
            if self.ther_schedule[4] !='' and self.ther_schedule[4] is not None:
                pnts_list = self.ther_schedule[4].split('-')
                self.ther_plan_list_maker(parent_frame,v_layout,pnts_list)


    def on_pnt_plan_day_tab_change(self,tab_index):
        make_list = False

        if tab_index==0:
            parent_frame = self.pnt_sch_frame_mon
            v_layout = self.verticalLayout_41
            
            if self.pnt_schedule[0] !='' and self.pnt_schedule[0] is not None:
                ther_dat = self.get_pnt_plan_details(0)
                ther_name,ther_apnt_time,ther_prof_name=ther_dat[0],ther_dat[1],ther_dat[2]
                make_list = True

        elif tab_index==1:
            parent_frame = self.pnt_sch_frame_tue
            v_layout = self.verticalLayout_42
           
            if self.pnt_schedule[1] !='' and self.pnt_schedule[1] is not None:
                ther_dat = self.get_pnt_plan_details(1)
                ther_name,ther_apnt_time,ther_prof_name=ther_dat[0],ther_dat[1],ther_dat[2]
                make_list = True
                
                
        elif tab_index==2:
            parent_frame = self.pnt_sch_frame_wed
            v_layout = self.verticalLayout_44
           
            if self.pnt_schedule[2] !='' and self.pnt_schedule[2] is not None:
                ther_dat = self.get_pnt_plan_details(2)
                ther_name,ther_apnt_time,ther_prof_name=ther_dat[0],ther_dat[1],ther_dat[2]
                make_list = True

                
        elif tab_index==3:
            parent_frame = self.pnt_sch_frame_thur
            v_layout = self.verticalLayout_46
            
            if self.pnt_schedule[3] !='' and self.pnt_schedule[3] is not None:
                ther_dat = self.get_pnt_plan_details(3)
                ther_name,ther_apnt_time,ther_prof_name=ther_dat[0],ther_dat[1],ther_dat[2]
                make_list = True

                
        elif tab_index==4:
            parent_frame = self.pnt_sch_frame_fri
            v_layout = self.verticalLayout_48
            
            if self.pnt_schedule[4] !='' and self.pnt_schedule[4] is not None:
                ther_dat = self.get_pnt_plan_details(4)
                ther_name,ther_apnt_time,ther_prof_name=ther_dat[0],ther_dat[1],ther_dat[2]
                make_list = True


        
        self.clear_layout(v_layout)
        if make_list:
            pnt_plan_temp = self.create_pnt_plan_list(parent_frame,ther_name,ther_prof_name,ther_apnt_time)
            v_layout.addWidget(pnt_plan_temp)

            pnt_plan_template_v_spacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            v_layout.addItem(pnt_plan_template_v_spacer) 
                
        
    def job_add_click(self):
        pro_name =  self.job_name_input.text()
        self.job_name_input.clear()
        j_id = f"PRO_{self.job_id}"
        if pro_name != "":
            self.db_cursor.execute("INSERT INTO job_ids VALUES (%s,%s)",(j_id,pro_name))
            self.db_connection.commit()
        self.job_id+=1
        self.read_jobsFromDb()
        self.CHANGED=True

    
    def job_edit_click(self,row_num):

        self.add_edit_stack.setCurrentIndex(1)

        gui_job_id = self.jobs_table.item(row_num,0)
        self.gui_job_id_text = gui_job_id.text()

        gui_job_name = self.jobs_table.item(row_num,1)
        self.gui_job_nametext = gui_job_name.text()


        self.job_new_name_input.setText(self.gui_job_nametext)
        self.job_id_label.setText(f"ID: {self.gui_job_id_text}") 

        

    def job_edit_save_click(self):
        
        new_name = self.job_new_name_input.text()
        if new_name!="":
            self.db_cursor.execute("UPDATE job_ids SET name=%s WHERE ID = %s",(new_name,self.gui_job_id_text))
            self.db_connection.commit()
            self.read_jobsFromDb()
        self.CHANGED=True


    def change_job_stackindex(self):
        self.add_edit_stack.setCurrentIndex(0)
   

    def job_delete_click(self,row_num):
        self.db_cursor.execute("DELETE FROM job_ids WHERE ID =%s",(self.job_id_data[row_num][0],))
        for row in self.job_id_data[row_num+1:]:
            new_id = f"PRO_{int(row[0].split('_')[1])-1}"
            self.db_cursor.execute("UPDATE job_ids SET ID = %s WHERE ID = %s",(new_id,row[0]))
        self.db_connection.commit()
        self.CHANGED=True

        self.read_jobsFromDb()

    def read_therapistFromDb(self):
        self.db_cursor.execute("SELECT * FROM therapists")
        
        self.therapists_data = self.db_cursor.fetchall()
        self.therapist_id = len(self.therapists_data)+1

        return self.therapists_data

    def read_patientsFromdb(self):
        self.db_cursor.execute("SELECT * FROM patients")
        
        self.patients_data = self.db_cursor.fetchall()
        self.patient_id = len(self.patients_data)+1

        return self.patients_data

    def add_therapist_button_click(self):
        ther_name = self.therapist_name_text.text()
        ther_address = self.therapist_addr_text.toPlainText()
        ther_prof = self.therapist_prof_dropdown.currentText()
        avail_days = ""
        avail_days_list = []
        if self.mon_check.isChecked():
            avail_days_list.append("Mo")
        if self.tue_check.isChecked():
            avail_days_list.append("Tu")
        if self.wed_check.isChecked():
            avail_days_list.append("We")
        if self.thur_check.isChecked():
            avail_days_list.append("Th")
        if self.fri_check.isChecked():
            avail_days_list.append("Fr")

        avail_days = ", ".join(avail_days_list)

        from_time = self.from_time_edit.time().toString("HH:mm")
        to_time = self.to_time_edit.time().toString("HH:mm")

        if ther_name!="" and ther_address!="":
            self.db_cursor.execute("SELECT ID from job_ids WHERE name= %s",(ther_prof,))
            ther_pro_id = self.db_cursor.fetchall()[0][0]
            ther_id = f"THER_{self.therapist_id}"
            self.db_cursor.execute("INSERT INTO therapists VALUES (%s,%s,%s,%s)",(ther_id,ther_name,ther_address,ther_pro_id))
            self.db_cursor.execute("INSERT INTO therapist_availability VALUES (%s,%s,%s,%s,%s)",(ther_id,ther_name,avail_days,from_time,to_time))
            self.db_connection.commit()
            self.therapist_id+=1

            self.therapist_name_text.clear()
            self.therapist_addr_text.clear()
            self.therapist_prof_dropdown.setCurrentIndex(0)
            self.mon_check.setChecked(False)
            self.tue_check.setChecked(False)
            self.wed_check.setChecked(False)
            self.thur_check.setChecked(False)
            self.fri_check.setChecked(False)
            self.CHANGED=True


    def add_patient_button_click(self):
        

        pat_name = self.patient_name_text.text()
        pat_address = self.patient_addr_text.toPlainText()
        prof_reqd = self.prof_reqd_combo.currentData()
        avail_days_list = []
        if self.mon_check_patient.isChecked():
            avail_days_list.append("Mo")
        if self.tue_check_patient.isChecked():
            avail_days_list.append("Tu")
        if self.wed_check_patient.isChecked():
            avail_days_list.append("We")
        if self.thur_check_patient.isChecked():
            avail_days_list.append("Th")
        if self.fri_check_patient.isChecked():
            avail_days_list.append("Fr")

        avail_days = ", ".join(avail_days_list)
        
        if pat_name!="" and pat_address!="":

            pat_id = f"PNT_{self.patient_id}"

            self.db_cursor.execute("INSERT INTO patients VALUES (%s,%s,%s,%s)",(pat_id,pat_name,pat_address,avail_days))
            
            reqd_prof_list = []
            for prof_name in prof_reqd:
                self.db_cursor.execute("SELECT ID from job_ids WHERE name= %s",(prof_name,))
                reqd_prof_list.append(self.db_cursor.fetchall()[0][0])
            reqd_prof = ','.join(reqd_prof_list)

            self.db_cursor.execute("INSERT INTO therapy_plans VALUES (%s,%s)",(pat_id,reqd_prof))
            self.db_connection.commit()
            
            self.patient_id+=1

            self.patient_name_text.clear()
            self.patient_addr_text.clear()
            self.prof_reqd_combo.setCurrentIndex(-1)
            self.prof_reqd_combo.clear_selection()
            self.mon_check_patient.setChecked(False)
            self.tue_check_patient.setChecked(False)
            self.wed_check_patient.setChecked(False)
            self.thur_check_patient.setChecked(False)
            self.fri_check_patient.setChecked(False)
            self.CHANGED=True


    def view_plan_button_click(self,ther_id):
        self.ther_schedule_stack.setCurrentIndex(1)
        self.db_cursor.execute("SELECT Therapist from therapists WHERE ID=%s",(ther_id,))
        ther_name = self.db_cursor.fetchall()[0][0]
        self.ther_plan_name_label.setText(ther_name)
        self.db_cursor.execute("SELECT Mo,Tu,We,Th,Fr FROM therapist_schedule WHERE ID=%s",(ther_id,))
        self.ther_schedule = self.db_cursor.fetchall()[0]
        self.ther_plan_tabs.setCurrentIndex(0)
        self.on_ther_plan_day_tab_change(0)
    
    def view_pnt_plan_button_click(self,pnt_id):
        self.pnt_schedule_stack.setCurrentIndex(1)
        self.db_cursor.execute("SELECT Patient from patients WHERE ID=%s",(pnt_id,))
        patient_name = self.db_cursor.fetchall()[0][0]
        self.pnt_plan_name_label.setText(patient_name)
        self.db_cursor.execute("SELECT Mo,Tu,We,Th,Fr FROM patient_schedule WHERE ID=%s",(pnt_id,))
        self.pnt_schedule = self.db_cursor.fetchall()[0]
        self.pnt_plan_tabs.setCurrentIndex(0)
        self.on_pnt_plan_day_tab_change(0)


    def on_click_db_detail_save_button(self):
        db_dat_file = open("db_info.dat","wb")

        db_dat = ['','','','']
        db_dat[0] = self.host_addr_text.text()
        db_dat[1] = self.user_name_text.text()
        db_dat[2] = self.pass_text.text()
        db_dat[3] = self.db_name_text.text()
        self.MYSQL_HOST,self.MYSQL_USER,self.MYSQL_PASSWORD,self.MYSQL_DB = db_dat[0],db_dat[1],db_dat[2],db_dat[3]
        
        if '' not in db_dat:
            pickle.dump(db_dat,db_dat_file)
            self.db_details_ready=True
            self.ready_gui()
            db_dat_file.close()

    def on_ther_edit_click(self,ther_id,therapist_name,job_name,ther_address,avail_days,avail_time):
        self.therapists_tab.setCurrentIndex(0)
        self.add_edit_ther_stack.setCurrentIndex(1)
        

        self.therapist_prof_dropdown_edit.clear()
        self.therapist_addr_text_edit.clear()
        self.mon_check_edit.setChecked(False)
        self.tue_check_edit.setChecked(False)
        self.wed_check_edit.setChecked(False)
        self.thur_check_edit.setChecked(False)
        self.fri_check_edit.setChecked(False)

        
        from_hr = int(avail_time.split("-")[0].split(":")[0].strip())
        from_min = int(avail_time.split("-")[0].split(":")[1].strip())
        to_hr = int(avail_time.split("-")[1].split(":")[0].strip())
        to_min = int(avail_time.split("-")[1].split(":")[1].strip())

       


        self.ther_edit_id.setText(f"Therapist ID: {ther_id}")
        self.therapist_name_text_edit.setText(therapist_name)
        self.therapist_addr_text_edit.append(ther_address)
        AllItems = [self.therapist_prof_dropdown.itemText(i) for i in range(self.therapist_prof_dropdown.count())]
        selected_index = AllItems.index(job_name)
        for item in AllItems:
            self.therapist_prof_dropdown_edit.addItem(item)
            self.therapist_prof_dropdown_edit.setCurrentIndex(selected_index)
        self.from_time_edit_edit.setTime(QtCore.QTime(from_hr,from_min))
        self.to_time_edit_edit.setTime(QtCore.QTime(to_hr,to_min))
            

        
        days = avail_days.split(" ")
        if 'Mo' in days:
            self.mon_check_edit.setChecked(True)
        if 'Tu' in days:
            self.tue_check_edit.setChecked(True)
        if 'We' in days:
            self.wed_check_edit.setChecked(True)
        if 'Th' in days:
            self.thur_check_edit.setChecked(True)
        if 'Fr' in days:
            self.fri_check_edit.setChecked(True)
    
    def on_click_edit_therapist_save_button(self):
        
        ther_id = self.ther_edit_id.text().split(":")[1].strip()
        ther_name = self.therapist_name_text_edit.text()
        ther_address = self.therapist_addr_text_edit.toPlainText()
        ther_prof = self.therapist_prof_dropdown_edit.currentText()
        avail_days_list = []
        if self.mon_check_edit.isChecked():
            avail_days_list.append("Mo")
        if self.tue_check_edit.isChecked():
            avail_days_list.append("Tu")
        if self.wed_check_edit.isChecked():
            avail_days_list.append("We")
        if self.thur_check_edit.isChecked():
            avail_days_list.append("Th")
        if self.fri_check_edit.isChecked():
            avail_days_list.append("Fr")

        avail_days = ", ".join(avail_days_list)

        from_time = self.from_time_edit_edit.time().toString("HH:mm")
        to_time = self.to_time_edit_edit.time().toString("HH:mm")

        if ther_name!="" and ther_address!="":
            # print(ther_id,ther_name,ther_address,ther_prof,avail_days,from_time,to_time)
            
            self.db_cursor.execute("SELECT ID from job_ids WHERE name= %s",(ther_prof,))
            ther_pro_id = self.db_cursor.fetchall()[0][0]
            self.db_cursor.execute("UPDATE therapists SET Therapist=%s,Therapist_Address=%s,Profession=%s WHERE ID=%s",(ther_name,ther_address,ther_pro_id,ther_id))
            self.db_cursor.execute("UPDATE therapist_availability SET Therapist=%s,Days=%s,Time_From=%s,Time_To=%s WHERE ID=%s",(ther_name,avail_days,from_time,to_time,ther_id))
            self.db_connection.commit()
            self.CHANGED=True
        

    def on_ther_delete_click(self,ther_id):
        self.db_cursor.execute("SELECT ID FROM therapists")
        ther_ids = self.db_cursor.fetchall()
        ther_ids_list=[]
        for i in ther_ids:
            ther_ids_list.append(i[0])
        ther_ids_list.sort(key=lambda x:int(x.split("_")[1]))
        print(ther_ids_list)
        self.db_cursor.execute("DELETE FROM therapists WHERE ID=%s",(ther_id,))
        self.db_cursor.execute("DELETE FROM therapist_availability WHERE ID=%s",(ther_id,))
        for id in ther_ids_list[ther_ids_list.index(ther_id)+1:]:
            print(f"THER_{int(id.split('_')[1])-1}")
            self.db_cursor.execute("UPDATE therapists SET ID = %s WHERE ID=%s",(f"THER_{int(id.split('_')[1])-1}",ther_id))
            self.db_cursor.execute("UPDATE therapist_availability SET ID = %s WHERE ID=%s",(f"THER_{int(id.split('_')[1])}",ther_id))
        self.db_connection.commit()
        self.on_thrapist_tab_change(1)
        self.CHANGED=True


    def on_patient_edit_click(self,pnt_id,pnt_name,pnt_address,pnt_prof,avail_days):
        self.patient_view_tab.setCurrentIndex(0)
        self.patient_edit_view_stack.setCurrentIndex(1)
        pnt_prof = pnt_prof.split("\n")
        

        prev_options = self.prof_reqd_combo.currentOptions

        self.prof_reqd_combo_edit_page.clear()
        self.patient_addr_text_edit.clear()
        self.mon_check_patient_edit.setChecked(False)
        self.tue_check_patient_edit.setChecked(False)
        self.wed_check_patient_edit.setChecked(False)
        self.thur_check_patient_edit.setChecked(False)
        self.fri_check_patient_edit.setChecked(False)

        

        self.patient_edit_id.setText(f"Patient ID: {pnt_id}")
        self.patient_name_text_edit.setText(pnt_name)
        self.patient_addr_text_edit.append(pnt_address)
        self.prof_reqd_combo_edit_page.addItems(prev_options)

        for chosenOpt in pnt_prof:
            ind = prev_options.index(chosenOpt)
            self.prof_reqd_combo_edit_page.model().item(ind).setCheckState(QtCore.Qt.Checked)


        days = avail_days.split(" ")
        if 'Mo' in days:
            self.mon_check_patient_edit.setChecked(True)
        if 'Tu' in days:
            self.tue_check_patient_edit.setChecked(True)
        if 'We' in days:
            self.wed_check_patient_edit.setChecked(True)
        if 'Th' in days:
            self.thur_check_patient_edit.setChecked(True)
        if 'Fr' in days:
            self.fri_check_patient_edit.setChecked(True)
    
    def on_click_edit_patient_save_button(self):
        
        pnt_id = self.patient_edit_id.text().split(":")[1].strip()
        pnt_name = self.patient_name_text_edit.text()
        pnt_address = self.patient_addr_text_edit.toPlainText()
        pnt_profs = self.prof_reqd_combo_edit_page.currentData()

        reqd_prof_list = []
        for prof_name in pnt_profs:
            self.db_cursor.execute("SELECT ID from job_ids WHERE name= %s",(prof_name,))
            reqd_prof_list.append(self.db_cursor.fetchall()[0][0])
        reqd_prof = ','.join(reqd_prof_list)

        print(reqd_prof)

        avail_days_list = []
        if self.mon_check_patient_edit.isChecked():
            avail_days_list.append("Mo")
        if self.tue_check_patient_edit.isChecked():
            avail_days_list.append("Tu")
        if self.wed_check_patient_edit.isChecked():
            avail_days_list.append("We")
        if self.thur_check_patient_edit.isChecked():
            avail_days_list.append("Th")
        if self.fri_check_patient_edit.isChecked():
            avail_days_list.append("Fr")

        avail_days = ", ".join(avail_days_list)

        if pnt_name!="" and pnt_address!="":
            self.db_cursor.execute("UPDATE patients SET Patient=%s, Patient_Adress=%s, Patient_Availability=%s WHERE ID=%s",(pnt_name,pnt_address,avail_days,pnt_id))
            self.db_cursor.execute("UPDATE therapy_plans SET Required_Profession=%s WHERE ID=%s",(reqd_prof,pnt_id))
            
        self.db_connection.commit()
        self.CHANGED=True

            

    def on_patient_delete_click(self,pnt_id):
        self.db_cursor.execute("SELECT ID FROM patients")
        pnt_ids = self.db_cursor.fetchall()
        pnt_ids_list=[]
        for i in pnt_ids:
            pnt_ids_list.append(i[0])
        pnt_ids_list.sort(key=lambda x:int(x.split("_")[1]))
        print(pnt_ids_list)
        self.db_cursor.execute("DELETE FROM patients WHERE ID=%s",(pnt_id,))
        self.db_cursor.execute("DELETE FROM therapy_plans WHERE ID=%s",(pnt_id,))
        for id in pnt_ids_list[pnt_ids_list.index(pnt_id)+1:]:
            print(f"THER_{int(id.split('_')[1])-1}")
            self.db_cursor.execute("UPDATE patients SET ID = %s WHERE ID=%s",(f"PNT_{int(id.split('_')[1])-1}",pnt_id))
            self.db_cursor.execute("UPDATE therapy_plans SET ID = %s WHERE ID=%s",(f"PNT_{int(id.split('_')[1])}",pnt_id))
        self.db_connection.commit()
        self.on_patient_tab_change(1)
        self.CHANGED=True


    def on_click_back_add_button_edit_patient(self):
        self.patient_edit_view_stack.setCurrentIndex(0)

    
    def ther_edit_back_click(self):
        self.add_edit_ther_stack.setCurrentIndex(0)

    def back_ther_view_page_button_click(self):
        self.ther_schedule_stack.setCurrentIndex(0)
    
    def back_pnt_view_page_button_click(self):
        self.pnt_schedule_stack.setCurrentIndex(0)

    def clear_layout(self,layout):
        for i in reversed(range(layout.count())): 
                widget = layout.itemAt(i).widget()
                if widget is not None:
                    widget.setParent(None)
                else:
                    layout.takeAt(i)
                 
                
    
    def ther_plan_list_maker(self,parent_frame,v_layout,pnts_list):
        for pnt_id in pnts_list:
            self.db_cursor.execute("SELECT Patient,Patient_Adress FROM patients WHERE ID = %s",(pnt_id,))
            pnt_dat = self.db_cursor.fetchall()
            pnt_no = pnts_list.index(pnt_id)+1
            pnt_name = pnt_dat[0][0]
            pnt_address = pnt_dat[0][1]
            pnt = self.create_ther_plan_list(parent_frame,str(pnt_no),pnt_name,pnt_address)
            v_layout.addWidget(pnt)

        verticalSpacer_3 = QtWidgets.QSpacerItem(20, 88, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        v_layout.addItem(verticalSpacer_3)
    
    def get_pnt_plan_details(self,index):
            
            ther_and_time = self.pnt_schedule[index].split('-')
            ther_id = ther_and_time[0]
            temp_time = ther_and_time[1].split(":")
            ther_apnt_time = temp_time[0]+":"+temp_time[1]

            self.db_cursor.execute("SELECT Therapist,Profession FROM therapists WHERE ID=%s ",(ther_id,))
            ther_dat = self.db_cursor.fetchall()
            ther_name = ther_dat[0][0]
            ther_prof_id = ther_dat[0][1]
            self.db_cursor.execute("SELECT name FROM job_ids WHERE ID=%s",(ther_prof_id,))
            ther_prof_name = self.db_cursor.fetchall()[0][0]

            return ther_name,ther_apnt_time,ther_prof_name

    def do_nothing(self):
        return
def main():
    
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec_()


if __name__ == '__main__':
    main()