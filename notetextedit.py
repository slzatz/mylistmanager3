import sys
import webbrowser
import html
import markdown2 as markdown
from functools import partial

from PyQt5 import QtCore, QtGui, QtWidgets
Qt = QtCore.Qt

class NoteTextEdit(QtWidgets.QTextEdit): #(QTextEdit):QTextBrowser

    #(Bold, Italic, H2, Pre, Num_List, Bullet_List, H1, Remove, Plain, Code, H3, Anchor) = list(range(12))

    def __init__(self, parent=None):
        super(NoteTextEdit, self).__init__(parent)

        self.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
        self.setTabChangesFocus(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumWidth(300)

        self.setMouseTracking(True)

        font = QtGui.QFont()
        font.setPointSize(10)
        font.setFamily("helvetica")
        self.document().setDefaultFont(font)

        self.font = font

        #self.setOpenExternalLinks(True) #only a method of QTextBrowser (and couldn't get it to work so rolled my own)
        
        self.highlighter = MyHighlighter(self) ############ 

    def toggleItalic(self):
        if self.which_header():
            return

        italic = self.fontItalic()
        cursor = self.textCursor()
        char_format = QtGui.QTextCharFormat()
        char_format.setFont(self.font)
        char_format.setFontItalic(not italic)
        cursor.setCharFormat(char_format)

    def make_plain_text(self):
        cursor = self.textCursor()

        char_format = QtGui.QTextCharFormat()
        char_format.setFont(self.font)

        cursor.setCharFormat(char_format)

        block_format = QtGui.QTextBlockFormat()
        block_format.setNonBreakableLines(False)
        cursor.setBlockFormat(block_format)

    def make_pre_block(self):
        cursor = self.textCursor()
        block_format = cursor.blockFormat()

        if block_format.nonBreakableLines():
            block_format.setNonBreakableLines(False)
            cursor.setBlockFormat(block_format)
            char_format = QtGui.QTextCharFormat()
            char_format.setFontFixedPitch(False)
            cursor.setCharFormat(char_format)
        else:
            block_format.setNonBreakableLines(True)
            cursor.setBlockFormat(block_format)

            char_format = QtGui.QTextCharFormat()
            char_format.setFontFixedPitch(True)
            cursor.setCharFormat(char_format)

    def toggleBold(self):
        if self.which_header():
            return

        bold = self.fontWeight() > QtGui.QFont.Normal
        cursor = self.textCursor()
        char_format = QtGui.QTextCharFormat()
        char_format.setFont(self.font)
        char_format.setFontWeight(QtGui.QFont.Normal if bold else QtGui.QFont.Bold)
        cursor.setCharFormat(char_format)

    def toggleCode(self):
        if self.which_header():
            return
        cursor = self.textCursor()
        #if not cursor.hasSelection():
        #    return

        char_format = cursor.charFormat()

        if char_format.fontFixedPitch():
            # didn't do exhaustive testing but appear to need both statements
            char_format.setFontFixedPitch(False)
            char_format.setFontFamily("helvetica")
        else:
            char_format.setFontFixedPitch(True)
            char_format.setFontFamily("Courier New") # probably should be "Courier New,courier"

        char_format.setFontItalic(False)
        char_format.setFontWeight(QtGui.QFont.Normal)

        cursor.setCharFormat(char_format)

        #The below also works but seems a little more kludgy
        #text = unicode(cursor.selectedText()) # need unicode for if below
        #text = '<code>{0}</code>'.format(text)
        #cursor.removeSelectedText() #cursor.deleteChar()
        #cursor.insertHtml(text) # also self.insertHtml should work

    def create_anchor(self):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return
        text = cursor.selectedText() # 03/13/2010

        if text.startswith('https://'):
            text = '<a href="{0}">{1}</a> '.format(text, text[8:])
        elif text.startswith('http://'):
            text = '<a href="{0}">{1}</a> '.format(text, text[7:])
        else:
            text = '<a href="http://{0}">{0}</a> '.format(text)

        # the below works but doesn't pick up highlighting of an anchor - would have to do the underlining and blue color
        #format = QTextCharFormat()
        #format.setAnchor(True)
        #format.setAnchorHref(text)
        #cursor.setCharFormat(format)
        ##self.setTextCursor(cursor)

        #this also works and generates highlighting
        cursor.deleteChar()
        cursor.insertHtml(text) # also self.insertHtml should work

    def create_numbered_list(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.createList(QtGui.QTextListFormat.ListDecimal)

    def create_bulleted_list(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.createList(QtGui.QTextListFormat.ListDisc)

    def make_heading(self, heading):
        # not finished
        cursor = self.textCursor()
        cursor.select(QtGui.QTextCursor.BlockUnderCursor) #QTextCursor.LineUnderCursor

        char_format = QtGui.QTextCharFormat()
        #font = self.font this is a problem  because it changes self.font gets changed below
        font = QtGui.QFont()
        font.setFamily("helvetica")
        font.setPointSize({1:20, 2:15, 3:12}[heading])
        font.setBold(True)
        char_format.setFont(font)

        cursor.setCharFormat(char_format)

    def increment_heading(self):
        header = self.which_header()
        if header=='H3':
            self.make_heading(2)
        elif header=='H2':
            self.make_heading(1)
        elif header=='H1':
            cursor = self.textCursor()
            pos = cursor.position()
            cursor.select(QtGui.QTextCursor.BlockUnderCursor)
            self.setTextCursor(cursor) #need this
            self.make_plain_text()
            cursor = self.textCursor()
            cursor.clearSelection()
            cursor.setPosition(pos)
            self.setTextCursor(cursor) #need this
        else:
            self.make_heading(3)

    def sizeHint(self): # this makes the text box taller when launched than if I don't have it
        return QtCore.QSize(self.document().idealWidth() + 5, self.maximumHeight())

    def contextMenuEvent__(self, event): # this catches the context menu right click
        self.textEffectMenu()

    def fontFixedPitch(self):
        cursor = self.textCursor()
        format_ = cursor.charFormat()
        return format_.fontFixedPitch()

    def which_header(self):
        cursor = self.textCursor()
        char_format = cursor.charFormat()
        ps = char_format.font().pointSize()
        return {20:'H1', 15:'H2', 12:'H3'}.get(ps)

    def textEffectMenu__(self):
        #format_ = self.currentCharFormat()
        cursor = self.textCursor()
        blockformat = cursor.blockFormat()
        menu = QtGui.QMenu("Text Effect")
        for text, shortcut, data, checked in (
                ("&Bold", "Ctrl+B", NoteTextEdit.Bold,
                 self.fontWeight() > QFont.Normal),
                ("&Italic", "Ctrl+I", NoteTextEdit.Italic,
                 self.fontItalic()),
                ("&Monospaced", None, NoteTextEdit.Code,
                 self.fontFixedPitch())
                ): 

            action = menu.addAction(text, self.setTextEffect)
            if shortcut is not None:
                action.setShortcut(QKeySequence(shortcut)) # because it's textedit,don't think these do anything
            action.setData(data)
            action.setCheckable(True)
            action.setChecked(checked)

        menu.addSeparator()

        action = menu.addAction("Anchor", self.setTextEffect)
        action.setData(NoteTextEdit.Anchor)

        action = menu.addAction("Code Block", self.setTextEffect)
        action.setData(NoteTextEdit.Pre)
        #action.setCheckable(False)

        action = menu.addAction("Numbered List", self.setTextEffect)
        action.setData(NoteTextEdit.List)
        #action.setCheckable(False)

        #header_action = QAction('Header')
        header_menu = QtGui.QMenu("Header")
        action = header_menu.addAction('H1', self.setTextEffect)
        action.setData(NoteTextEdit.H1)
        action.setCheckable(True)
        action.setChecked(self.which_header()=='H1')

        action = header_menu.addAction('H2', self.setTextEffect)
        action.setData(NoteTextEdit.H2)
        action.setCheckable(True)
        action.setChecked(self.which_header()=='H2')

        action = header_menu.addAction('H3', self.setTextEffect)
        action.setData(NoteTextEdit.H3)
        action.setCheckable(True)
        action.setChecked(self.which_header()=='H3')

        action = menu.addAction("Remove All Formatting", self.setTextEffect)
        action.setData(NoteTextEdit.Remove)
        #action.setCheckable(False)

        menu.addMenu(header_menu)

        menu.addSeparator()

        self.ensureCursorVisible()
        menu.exec_(self.viewport().mapToGlobal(self.cursorRect().center()))

    def setTextEffect__(self):
        action = self.sender()

        d = {
               NoteTextEdit.Bold: self.toggleBold,
               NoteTextEdit.Italic: self.toggleItalic,
               NoteTextEdit.Code: self.toggleCode,
               NoteTextEdit.Anchor:  self.create_anchor,
               NoteTextEdit.Pre: self.make_pre_block,
               NoteTextEdit.Remove: self.make_plain_text,
               NoteTextEdit.Num_List: self.create_numbered_list,
               NoteTextEdit.Bullet_List: self.create_bulleted_list,
               NoteTextEdit.H1: partial(self.make_heading, 1),
               NoteTextEdit.H2: partial(self.make_heading, 2),
               NoteTextEdit.H3: partial(self.make_heading, 3)
               }

        if action is not None and isinstance(action, QAction):
            d[action.data()]()    

    def mouseMoveEvent(self, event):
        pos = event.pos()
        anch = self.anchorAt(pos)
        self.viewport().setCursor(Qt.PointingHandCursor if anch else Qt.IBeamCursor)
        QtWidgets.QTextEdit.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event):
        pos = event.pos()
        url = self.anchorAt(pos)

        if url:            
            if not url.startswith('http'): #linux seems to need this
                url = 'http://{0}'.format(url)
            #webbrowser.open(str(url), new=2, autoraise=True)
            webbrowser.open(url, new=2, autoraise=True) # 03/13/2010
        else:
            QtWidgets.QTextEdit.mouseReleaseEvent(self, event)

    def insertFromMimeData(self, source):
        # note sure really necessary since it actually appears to paste URLs correctly
        # I am stripping the http
        print("Paste")
        text = source.text()  #str(source.text())
        if len(text.split())==1 and (text.startswith('http://') or text.startswith('https://') or 'www' in text or '.com' in text or '.html' in text):
            if text.startswith('http://'):
                text = '<a href="{0}">{1}</a> '.format(text, text[7:])
            elif text.startswith('https://'):
                text = '<a href="{0}">{1}</a> '.format(text, text[8:])
            else:
                text = '<a href="http://{0}">{0}</a> '.format(text)
            self.insertHtml(text)
        else:   
            QtWidgets.QTextEdit.insertFromMimeData(self, source)

    def toSimpleHtml(self):
        pre = False
        para = '' 
        black = QtGui.QColor(Qt.black)
        block = self.document().begin() # block is like a para; text fragment is sequence of same char format
        while block.isValid():
            html = '' 
            iterator = block.begin()
            while iterator != block.end():
                fragment = iterator.fragment()
                if fragment.isValid():
                    format_ = fragment.charFormat()
                    family = format_.fontFamily()
                    color = format_.foreground().color()
                    #text = html.escape(fragment.text()) # turns things like < into entities &lt;
                    text = fragment.text() # not sure escaping is necessary 

                    # If it's an anchor, don't want to do any other formatting
                    if format_.isAnchor():
                        text = '<a href="{0}">{0}</a> '.format(text)
                    else:
                        if format_.fontUnderline():
                            text = "<u>{0}</u>".format(text)
                        if format_.fontItalic():
                            text = "<i>{0}</i>".format(text)
                        if format_.fontWeight() > QFont.Normal:
                            text = "<b>{0}</b>".format(text)

                        if color != black or not family.isEmpty() and not block.blockFormat().nonBreakableLines():
                            attribs = ""
                            if color != black:
                                attribs += ' color="{0}"'.format(color.name())
                            if not family.isEmpty():
                                attribs += ' face="{0}"'.format(family)
                            text = "<font{0}>{1}</font>".format(attribs,text)
                    html += text
                iterator += 1

            if block.blockFormat().nonBreakableLines():
                if pre:
                    para += html+'\n'
                else:
                    para += '<pre>{0}{1}'.format(html,'\n')
                    pre = True
            else:
                if pre:
                    para += '</pre>\n<p>{0}</p>\n'.format(html) 
                    pre = False
                else:
                    para += '<p>{0}</p>\n'.format(html)


            block = next(block)

        if pre:
            para += '</pre>'

        return para 

    def toMarkdown(self):
        references = ''
        i = 1
        doc = ''
        block = self.document().begin() # block is like a para; text fragment is sequence of same char format
        is_list_line = False
        was_pre_line = False 
        while block.isValid():
            if block.blockFormat().nonBreakableLines():
                doc += '    '+block.text()+'\n'
                was_pre_line = True
            elif block.blockFormat().hasProperty(QtGui.QTextFormat.BlockTrailingHorizontalRulerWidth): 
                doc += '\n'+'----'+'\n\n' 
                was_pre_line = False
            else:
                if block.textList(): #? could also use block.blockFormat().isListFormat()
                    if block.textList().format().style() == QtGui.QTextListFormat.ListDecimal:
                        doc += '  '+block.textList().itemText(block) + ' ' 
                    else:
                        doc += '  - ' 
                para = ''
                iterator = block.begin()
                while iterator != block.end():
                    fragment = iterator.fragment()
                    if fragment.isValid():
                        char_format = fragment.charFormat()
                        #text = html.escape(fragment.text()) # turns chars like < into entities &lt;
                        text = fragment.text() ########################################################## 
                        text = text.replace('\u2028','  \n') # catches  u'\u2028 and replaces with markdown rep of <br /> may want to use QChar.LineSeparator
                        font_size = char_format.font().pointSize()

                        # a fragment can only be an anchor, italics, bold or mono

                        if char_format.isAnchor():
                            if text.startswith('http'):
                                references += "  [{0}]: {1}\n".format(i, text)
                            else:
                                references += "  [{0}]: {1}\n".format(i, char_format.anchorHref())                            

                            text = "[{0}][{1}]".format(text,i)
                            i+=1
                        elif font_size > 10:
                            if font_size > 15:
                                text = '#{0}'.format(text)
                            elif font_size > 12:
                                text = '##{0}'.format(text)
                            else:
                                text = '###{0}'.format(text)
                        elif char_format.fontFixedPitch(): #or format.fontFamily=='courier':
                            text = "`{0}`".format(text)
                        elif char_format.fontItalic():
                            text = "*{0}*".format(text)
                        elif char_format.fontWeight() > QtGui.QFont.Normal: #font-weight:600; same as for an H1; H1 font-size:xx-large; H1 20; H2 15 H3 12
                            text = "**{0}**".format(text)

                        para += text
                    iterator += 1

                    was_list_line = is_list_line
                    is_list_line =block.textList()

                    if (not is_list_line and was_list_line) or was_pre_line:
                        para = '\n'+para

                    was_pre_line = False  

                doc += para+'\n\n' if not is_list_line else para+'\n'
            block = block.next()
        return doc+references

class MyHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, parent=None):
        super(MyHighlighter, self).__init__(parent)
        self.parent = parent

        keyword_format = QtGui.QTextCharFormat()
        keyword_format.setForeground(Qt.darkBlue)
        keyword_format.setFontWeight(QtGui.QFont.Bold)
        self.keyword_format = keyword_format

        # in case highliter is called before setkeywords (not sure it ever would be)
        self.regex_keywords = []
        

    def highlightBlock(self, text):
        #print("In highlightBlock")
        for regex in self.regex_keywords:
            index = regex.indexIn(text)
            #print("initial index={0}".format(index))
            while index >= 0:
                length = regex.matchedLength()
                #print("length={0}".format(length))
                self.setFormat(index, length, self.keyword_format) #length
                #index = text.indexOf(regex, index + length )
                index = regex.indexIn(text, index + length)
                #print("subsequent index={0}".format(index))
        self.setCurrentBlockState(0)
    def setkeywords(self, keywords=None):
        
        self.regex_keywords = []
        
        if keywords == None:
            return
            
        for word in keywords:
            regex = QtCore.QRegExp("\\b" + word, Qt.CaseInsensitive)
            self.regex_keywords.append(regex)

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    note = NoteTextEdit()
    note.show()
    note.setWindowTitle("RichTextEdit")
    #note.setHtml(QString('<b>how</b> <i>are</i> you? <a href="www.medscape.com">www.medscape.com</a> I am <font color="#ff0000">fine</font>.  <p>      This is pretty <font face="helvetica">interesting</font>.</p>'))
    z ='''**how** *are* you? [www.medscape.com](www.medscape.com) I am `fine`.

This is pretty interesting.

        some code
            more code

> hello how are you
> I am fine -- what are you doing?
> not much, you?

Hello people

![Alt text][1]

[1]: http://l.yimg.com/a/i/ww/news/2010/01/07/smith.jpg
    '''
    zz = "**how** *are* you? [www.medscape.com](www.medscape.com) I am `fine`.\n\n###This is pretty interesting.\n\n    some code\n        <p>more code</p>\n\n\n\nhello\n\n1. One\n\n1. *Two*\n\n1. Three\n\nHello Again \n\n1. uno\n1. dos\n1. tres\n\n`Hello` Again\n\nab\nvd  \nzz  \n\nhello"
    print(z)
    html = markdown2.markdown(z)
    print(html)
    note.setHtml(html)
    #print note.viewport()
    #print(dir(note.viewport()))
    #print(note.widget())
    app.exec_()
    #print unicode(note.toHtml())
    #print unicode(note.toPlainText())
    #print unicode(note.toSimpleHtml())
    md = note.toMarkdown()
    print(markdown2.markdown(md))
    #print html2text.html2text(unicode(note.toHtml()))
    #print markdown.markdown(html2text.html2text(unicode(note.toHtml())))
    #note.toSimpleHtml2()
    #print note.document().size()
    #openExternalLinks qtextedit
    print(note.toHtml())


