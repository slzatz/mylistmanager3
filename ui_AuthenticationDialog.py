# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'AuthenticationDialog.ui'
#
# Created: Fri Dec 19 22:09:08 2014
#      by: PyQt5 UI code generator 5.3.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_AuthenticationDialog(object):
    def setupUi(self, AuthenticationDialog):
        AuthenticationDialog.setObjectName("AuthenticationDialog")
        AuthenticationDialog.resize(400, 165)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(AuthenticationDialog.sizePolicy().hasHeightForWidth())
        AuthenticationDialog.setSizePolicy(sizePolicy)
        AuthenticationDialog.setSizeGripEnabled(True)
        self.gridLayout = QtWidgets.QGridLayout(AuthenticationDialog)
        self.gridLayout.setObjectName("gridLayout")
        self.label = QtWidgets.QLabel(AuthenticationDialog)
        self.label.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label.setObjectName("label")
        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)
        self.usernameEdit = QtWidgets.QLineEdit(AuthenticationDialog)
        self.usernameEdit.setObjectName("usernameEdit")
        self.gridLayout.addWidget(self.usernameEdit, 0, 1, 1, 1)
        self.label_2 = QtWidgets.QLabel(AuthenticationDialog)
        self.label_2.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_2.setObjectName("label_2")
        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)
        self.passwordEdit = QtWidgets.QLineEdit(AuthenticationDialog)
        self.passwordEdit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.passwordEdit.setObjectName("passwordEdit")
        self.gridLayout.addWidget(self.passwordEdit, 1, 1, 1, 1)
        self.buttonBox = QtWidgets.QDialogButtonBox(AuthenticationDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.gridLayout.addWidget(self.buttonBox, 2, 0, 1, 2)

        self.retranslateUi(AuthenticationDialog)
        self.buttonBox.accepted.connect(AuthenticationDialog.accept)
        self.buttonBox.rejected.connect(AuthenticationDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(AuthenticationDialog)
        AuthenticationDialog.setTabOrder(self.usernameEdit, self.passwordEdit)
        AuthenticationDialog.setTabOrder(self.passwordEdit, self.buttonBox)

    def retranslateUi(self, AuthenticationDialog):
        _translate = QtCore.QCoreApplication.translate
        AuthenticationDialog.setWindowTitle(_translate("AuthenticationDialog", "Authentication Required"))
        self.label.setText(_translate("AuthenticationDialog", "email:"))
        self.usernameEdit.setToolTip(_translate("AuthenticationDialog", "Enter username"))
        self.label_2.setText(_translate("AuthenticationDialog", "Password:"))
        self.passwordEdit.setToolTip(_translate("AuthenticationDialog", "Enter password"))

