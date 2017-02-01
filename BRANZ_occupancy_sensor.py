'''0.2 Extra graph, added delete and edit times features and fixed a few bugs
'''

import serial
import os
import _winreg as winreg
import itertools
import time
from Tkinter import *
from datetime import datetime
import tkFileDialog
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
# implement the default mpl key bindings
from matplotlib.backend_bases import key_press_handler

class GUI(Frame):

    currentCom='-'
    fname=''
    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.parent = parent        
        self.parent.title("Grid Eye") #window title
        self.pack(fill=BOTH, expand=1)
        #forced to use pack manager as matplotlib doesn't work without it (has some buried pack methods in the library)
        
        #date plot
        lines = self.getNumbers(self.fname)
        self.fdot = Figure(figsize=(5, 4), dpi=100)
        if(lines):
            x=[]; y=[]; runs=0; labels=[]
            jump= len(lines)/2
            
            for line in lines:
                x.append(line[1])
                y.append(line[0])

            plt = self.fdot.add_subplot(111)
            
            dates = matplotlib.dates.date2num(x)
            plt.plot_date(dates, y)

        self.fdot.autofmt_xdate() #makes the x axis dates diagonal
        self.fdot.subplots_adjust(left=0.2, bottom =0.3)
        self.fdot.suptitle('Occupancy over time', fontsize=20)
        self.canvasdot = FigureCanvasTkAgg(self.fdot, master=parent)
        self.canvasdot.show()
        self.canvasdot.get_tk_widget().pack(side=TOP, fill=BOTH, expand=1)
        self.toolbar = NavigationToolbar2TkAgg(self.canvasdot, self)
        self.toolbar.update()
        self.canvasdot._tkcanvas.pack(side=TOP, fill=BOTH, expand=1,ipady=10, ipadx=10)

        self.canvasdot.mpl_connect('key_press_event', self.on_key_event)

        
        #pie  graph, this is mostly in the update method too and is unlikely to be called on init
        sizes = self.getResults(self.fname)
        
        self.fpie = Figure(figsize=(5, 4), dpi=100)
        if(sizes):
            plt = self.fpie.add_subplot(111)


            labels = ['Unoccupied', 'One Person', 'Two People']
            explode = (0.05, 0.05, 0.05)
            
            colors = ['skyblue', 'gold', 'orange']
            patches = plt.pie(sizes, colors=colors, autopct='%1.1f%%', explode= explode, labels=labels, shadow=False, startangle=90)
            plt.axis('equal')

        self.canvaspie = FigureCanvasTkAgg(self.fpie, master=parent)
        self.canvaspie.show()
        self.canvaspie.get_tk_widget().pack(side=TOP, fill=BOTH, expand=1)
        self.canvaspie._tkcanvas.pack(side=TOP, fill=BOTH, expand=1, ipady=10, ipadx=10)


        #Text box
        S = Scrollbar(self)
        self.T = Text(self, height=10, width=30)
        self.T.pack(side=LEFT, fill=BOTH, expand=1, )
        S.pack(side= LEFT, fill=Y)
        S.config(command=self.T.yview)
        self.T.config(yscrollcommand=S.set)
        self.T.insert(END, '')

        buts= Frame(self, width= 40) #this frame contains the buttons and status so they sit nicely with the stupid pack manager
        combut= Button(buts, text="Find COM port", command=self.findCom)
        combut.pack(fill=X, pady=10)
        lab= Label(buts, text = "Current COM port-")
        lab.pack(fill=X)
        self.comlabel= Label(buts, text = "-")
        self.comlabel.pack(fill=X)
        openbut= Button(buts, text="Load",  command=self.askopenfile)
        openbut.pack(fill=X, side=TOP)
        savebut= Button(buts, text="Save", command=self.asksavefile)
        savebut.pack(fill=X)
        delbut= Button(buts, text="Delete", command=self.removefile)
        delbut.pack(fill=X)
        rtcbut= Button(buts, text="Edit Timing Values", command=self.startTime)
        rtcbut.pack(fill=X)
        statusMessage= Label(buts, text = "Status:")
        statusMessage.pack(fill=X, pady=5)
        self.status= Label(buts, text= "-")
        self.status.pack(fill=X)
        buts.pack(side=LEFT, expand=1)
        

        # define options for opening or saving a file
        self.file_opt = options = {}
        options['defaultextension'] = '.csv'
        options['filetypes'] = [('Comma Seperated Value', '.csv'), ('text files', '.txt')]
        options['initialfile'] = self.fname
        options['parent'] = parent
        options['title'] = 'Save as'

    #Loads in a file from the sd card in the feather board
    def askopenfile(self):
        try:
            self.config(cursor="wait")
            self.status.config(text="loading")
            #start a serial connection
            self.ser = serial.Serial(
                    port= self.currentCom,
                    baudrate=115200,
                    bytesize=serial.EIGHTBITS,
                    timeout=3  )

            self.ser.flush()
            line="-";
            #wait for handshake character
            while 'A' not in line:
                line= self.ser.readline()
                line.strip();
                print('Connecting')
                print(line)


            files=[] #save a list of the files
            self.ser.write('list\0') #command for feather to send it's files
            time.sleep(1) #makes sure the list of files is available
            line= self.ser.readline(); #removes and extra bit
            
            while(line != "end\n"): #end is funnily enough the end of transmission signal
                files.append(line)
                line= self.ser.readline()

            fileObjects=[] #list of lists containing file name and size
            for f in files:
                temp=f.split() #split file string into name and size
                if len(temp)==2 and int(temp[1])>100:
                    fileObjects.append(temp)


            self.opentop= Toplevel(self, takefocus=True) #this is a pop up window, saved as a global variable so it can be closed in a different method
            self.opentop.geometry("500x500+800+150")
            self.opentop.title('Open')
            if(not fileObjects): #if there are no files
                l=Label(self.opentop, text= "No Files!\n Is SD inserted?", font=("",20, ""));
                l.pack()
                exitbut= Button(self.opentop,text='Close', command=lambda: self.opentop.destroy())
                #that command=lambda stops it actually going into the method before the button is pressed,
                #lambda is an empty function essentially, I don't know why tkinter makes you do this
                exitbut.pack()
                self.config(cursor="")
                self.status.config(text="No Files")
                return;
            
            rows=1
            cols=0
            for f in fileObjects:
                b= Button(self.opentop, text= f[0], command= lambda f=f: self.getfile(f[0], f[1]))
                #f=f is from http://stackoverflow.com/questions/10865116/python-tkinter-creating-buttons-in-for-loop-passing-command-arguments
                b.grid(row=rows, column=cols, sticky='EW', pady=5, padx=5) #I can use the grid manager now that I'm in a window without matplotlib
                l=Label(self.opentop, text= str(float(f[1])/1000)+' kB')
                l.grid(row=rows, column=cols+1, pady=5, padx=5)
                rows+=1
                if(rows>11): #rollover rows and go to next column
                    rows=1
                    cols+=2
            self.config(cursor="")
        except serial.SerialException: #pops up an annoying warning box if serial fails
            etop= Toplevel(self)
            etop.geometry("300x100+800+150")
            etop.title('WARNING')
            message= Message(etop, text= "Serial cannot connect, check Com port?")
            message.pack()
            exitbutton= Button(etop, text= "Ok", command= lambda: etop.destroy())
            exitbutton.pack()

    #retrieves file, given filename and size in Bytes
    def getfile(self, filename, size):
        sizeSoFar=0
        self.status.config(text="Reading")
        self.opentop.destroy() #close old pop up window

        self.fname=filename #save the current file in case it's needed later
        
        self.ser.write('fname '); self.ser.write(filename); self.ser.write('\0')
        f= open(filename, 'w')
        line= self.ser.readline();
        while(line != "end\n"):
            line= self.ser.readline()
            if 'A' not in line:
                f.write(line)
                sizeSoFar+= len(line.encode('utf-8')) #got off stack overflow, returns num of bytes in string
                s="Reading: " +str(int((float(sizeSoFar)/float(size))*100))+ "%"
                self.status.config(text=s)
                self.parent.update()
            
            
        f.close()
        self.update()
        self.ser.close() #close the serial connection once we're done
        self.status.config(text="Done")


    #saves the current file in a new location and deletes the old file
    def asksavefile(self):
        f = tkFileDialog.asksaveasfile(mode='w', **self.file_opt)
        if self.fname == '':
            self.status.config(text=" No Open File")
            nope = Toplevel(self, takefocus=True)
            nope.geometry("300x100+800+150")
            warningMsg= Message(nope, text= 'No file currently loaded!', width=300, padx=10, pady=10)
            warningMsg.pack()
            exitbut= Button(nope,text='Ok', command=lambda: nope.destroy())
            exitbut.pack()
            return
        old= open(self.fname, 'r')
        for line in old:
            f.write(line) #write the old file into the new file
        old.close()
        f.close()
        os.remove(self.fname) #delete the old file when we're done with it

    #connects to a com port
    def findCom(self):
        """this is a popup window"""
        self.top = Toplevel(self, takefocus=True)
        self.top.geometry("300x100+800+150")
        self.top.title('Choose a port')

        msg = Message(self.top, text='Choose a Com port', width=300, padx=10, pady=10)
        msg.grid(row=0, column=0, columnspan='8')
        
        comPorts=[]
        for i in enumerate_serial_ports():
            comPorts.append(i)
        if(len(comPorts)==1): #if only one automatically choose that one
            com= comPorts[0]
            self.setcurrentCom(com[0])
            self.status.config(text="Automatically chose Com")

        elif(len(comPorts)==0):
            noComMsg= Message(self.top, text= 'No available Com ports!', width=300, padx=10, pady=10)
            noComMsg.grid(row=1, column=0)

        exitbut= Button(self.top,text='Close', command=lambda: self.top.destroy())
        exitbut.grid(row=2, column=0)
            
        col=0
        for i in comPorts: #create a button for each available com port
            com=comPorts[col]
            combut=Button(self.top,text=com[0], command=lambda com=com: self.setcurrentCom(com[0]))
            combut.grid(row=1, column=col, pady=20)
            col+=1

    #sets the global variable of the current com port
    def setcurrentCom(self, com):
        self.currentCom= com
        self.update()
        self.top.destroy() #closes the pop up window in findCom


    #returns a list containing the count of each occupied state for the pie chart
    def getResults(self, filename):
        if(filename ==''):
            return False
        f= open(filename, 'r')
        lines=[]
        for line in f: #split into occupied decision and datetime
            l=line.strip('\r\n')
            l=l.split(",")  
            lines.append(l)

        twoCounter=0; oneCounter=0; noccupiedCounter=0;
        for i in lines:
            if(len(i)>0 and i[0]== 'Not Occupied'):
                noccupiedCounter+=1

            elif(len(i)>0 and i[0]== 'One Person'):
                oneCounter+=1

            elif(len(i)>0 and i[0]== 'Two People'):
                twoCounter+=1
        counters=[]
        counters.append(noccupiedCounter)
        counters.append(oneCounter)
        counters.append(twoCounter)
        return counters

    
    #returns a formatted list of the file for the dot plot
    def getNumbers(self, filename):
        if(filename ==''):
            return False
        f= open(filename, 'r')
        lines=[]
        for line in f:
            l=line.strip('\r\n')
            l=l.split(",")  
            lines.append(l)

        del lines[0]; del lines[-1]; del lines [-1] #removes first and last two entries which are file overhead

        for line in lines:
            line[1]=datetime.strptime(line[1], " %H:%M:%S %d:%m:%y ") #convert to datetime object
            #convert to number of people in space
            if(len(line)>0 and line[0]=="Not Occupied"):
                line[0]=0
            elif(len(line)>0 and line[0]=="One Person"):
                line[0]=1
            elif(len(line)>0 and line[0]== 'Two People'):
                line[0]=2
                
        return lines


    #wrapper method to delete a file off the SD card
    def removefile(self):
        #this part is basically the same as openfile
        try:
            self.config(cursor="wait")
            self.status.config(text="loading")
            self.ser = serial.Serial(
                    port= self.currentCom,
                    baudrate=115200,
                    bytesize=serial.EIGHTBITS,
                    timeout=3  )

            self.ser.flush()
            line="-";
            while 'A' not in line:
                line= self.ser.readline()
                line.strip();
                

            files=[] #save a list of the files
            self.ser.write('list\0')
            time.sleep(1)
            line= self.ser.readline();
            
            while(line != "end\n"):
                files.append(line)
                print(line)
                line= self.ser.readline()

            fileObjects=[] #list of lists containing file name and size
            for f in files:
                temp=f.split() #split file string into name and size
                if len(temp)==2 and int(temp[1])>100:
                    fileObjects.append(temp)

            self.opentop= Toplevel(self, takefocus=True)
            self.opentop.geometry("500x500+800+150")
            self.opentop.title('Delete')
            if(not fileObjects):
                l=Label(self.opentop, text= "No Files!\n Is SD inserted?", font=("",20, ""));
                l.pack()
                exitbut= Button(self.opentop,text='Close', command=lambda: self.opentop.destroy())
                exitbut.pack()
                self.config(cursor="")
                self.status.config(text="No Files")
                return;
            
            rows=1
            cols=0
            msg = Message(self.opentop, text='Note: This window will freeze until the file is deleted', padx=10, pady=10, width="600")
            msg.grid(row=0, column=0, columnspan='3')
            formatbut= Button(self.opentop, text= "Delete all", command= lambda: self.areYouSure(fileObjects))
            formatbut.grid(row=rows, column=cols, sticky='EW', pady=5, padx=5)
            rows+=1
            for f in fileObjects[:-1]:
                b= Button(self.opentop, text= f[0], command= lambda f=f: self.deletefile(f[0]))
                #f=f is from http://stackoverflow.com/questions/10865116/python-tkinter-creating-buttons-in-for-loop-passing-command-arguments
                b.grid(row=rows, column=cols, sticky='EW', pady=5, padx=5)
                l=Label(self.opentop, text= str(float(f[1])/1000)+' kB')
                l.grid(row=rows, column=cols+1, pady=5, padx=5)
                rows+=1
                if(rows>11):
                    rows=1
                    cols+=2
            self.config(cursor="")
            
            
        except serial.SerialException: #pops up an annoying warning box if serial fails
            etop= Toplevel(self)
            etop.geometry("300x100+800+150")
            etop.title('WARNING')
            message= Message(etop, text= "Serial cannot connect, check Com port?")
            message.pack()
            exitbutton= Button(etop, text= "Ok", command= lambda: etop.destroy())
            exitbutton.pack()


    #actually tells the feather to delete the file and waits for response
    def deletefile(self, filename):
        self.status.config(text="Deleting")
        self.fname=filename
        self.ser.write('delete '); self.ser.write(filename); self.ser.write('\0') #send the code to delete
        while(not self.ser.readline() == "removed\n"): #wait for file to be deleted
                time.sleep(0.2) #can't be too big otherwise may miss value

        self.ser.close()
        self.opentop.destroy()        
        self.status.config(text= "Deleted")


    #brings up a pop up box when the user tries to delete every file on the sd card
    def areYouSure(self, files):
        self.suretop= Toplevel(self)
        self.suretop.geometry("300x100+800+150")
        self.suretop.title('WARNING')
        message= Message(self.suretop, text= "Are you sure you want to delete ALL files on the SD card?", width=200)
        message.grid(row=0, column=0, columnspan=2)
        time.sleep(1)
        okbutton=  Button(self.suretop, text= "Ok", command= lambda: self.deleteAll(files))
        okbutton.grid(row=1, column=0)
        exitbutton= Button(self.suretop, text= "cancel", command= lambda: self.suretop.destroy())
        exitbutton.grid(row=1, column=1)

    #deletes everything off the sd card by calling deletefile
    def deleteAll(self,files):
        self.status.config(text="Deleting all")
        self.parent.update()
        self.ser.close()
        for f in files:
            #open serial port each time, is closed by delete file
            self.ser = serial.Serial(
                    port= self.currentCom,
                    baudrate=115200,
                    bytesize=serial.EIGHTBITS,
                    timeout=3  )
           
            self.deletefile(f[0])
        self.suretop.destroy()

    #wrapper method that changes every time value
    def startTime(self):
        self.clocktop= Toplevel(self)
        self.clocktop.geometry("500x200+800+150")
        self.clocktop.title('Choose time')
        message= Message(self.clocktop, text= "Enter the start time for this log file \n hh.mm.ss dd/mm/yy", width=300)
        message.pack(fill=X)
        self.e= Entry(self.clocktop) #this is what the user writes into, they have to use that specific format
        self.e.pack(fill=X)
        okbutton= Button(self.clocktop, text= "Ok", command= lambda: self.changeClock(self.e.get(), self.fname))
        okbutton.pack()
        exitbutton= Button(self.clocktop, text= "Close", command= lambda: self.clocktop.destroy())
        exitbutton.pack()

    #Actually changes time values
    def changeClock(self, startTime, filename):
        self.clocktop.destroy()
        if(filename ==''):
            return False
        startTime= datetime.strptime(startTime, "%H.%M.%S %d/%m/%y")
        f= open(filename, 'r')
        lines=[]
        for line in f:
            l=line.strip('\r\n')
            l=l.split(",")  
            lines.append(l)
            
        f.close()
        
        line0= "filename: " +filename + "\n"
        line1= "\n"
        line2= "end\n"
        del lines[0]
        del lines[-1]
        del lines [-1] #removes first and last two entries which are file overhead

        firstTime= lines[0][1]
        firstTime= datetime.strptime(firstTime, " %H:%M:%S %d:%m:%y ") #convert to datetime object
        delta= startTime- firstTime #difference in first time value and what we want the first time value to be

        f= open(filename, 'w')
        f.write(line0) #put the file overhead back
        for line in lines:
            line[1]=datetime.strptime(line[1], " %H:%M:%S %d:%m:%y ") #convert to datetime object
            newtime = line[1] + delta
            s=str(line[0]) + ", " #times in the file have to be formatted this way for the rest of this program
            year=str(newtime.year)
            s+= str(newtime.hour) +":"+ str(newtime.minute) +":"+ str(newtime.second) +" "+ str(newtime.day) +":"+ str(newtime.month) +":"+ year[-2] + year[-1]
            s+= " \n"
            f.write(s)

        f.write(line1); f.write(line2)
        f.close()
        self.update()
        self.status.config(text= "Times Updated")


    #handles key presses for the matplotlib toolbar
    def on_key_event(event):
        print('you pressed %s' % event.key)
        key_press_handler(event, self.canvasdot, toolbar)
        
    #updates the graphs and rest of GUI
    def update(self):
        self.comlabel.config(text=self.currentCom)
        if(self.fname!=''):
            self.T.delete(1.0, END)
            f= open(self.fname, 'r')
            lines=[]
            text=''
            for line in f:
                line=line.strip('\r\n')
                line+='\n' #first line needs an eol character
                self.T.insert(END, line)

        #date plot
        lines = self.getNumbers(self.fname)
        self.fdot.clear()
        plt = self.fdot.add_subplot(111)
        
        if(lines):
            x=[]; y=[]; runs=0; labels=[]
            jump= len(lines)/2
            
            for line in lines:
                x.append(line[1])
                y.append(line[0])
            
            dates = matplotlib.dates.date2num(x)
            plt.plot_date(dates, y)
            self.canvasdot.show()

        #piegraph
        sizes = self.getResults(self.fname)
        if(sizes):
            self.fpie.clear()
            plt = self.fpie.add_subplot(111)


            labels = ['Unoccupied', 'One Person', 'Two People']
            explode = (0.05, 0.05, 0.05)
            
            colors = ['skyblue', 'gold', 'orange']
            patches = plt.pie(sizes, colors=colors, autopct='%1.1f%%', explode= explode, labels=labels, shadow=False, startangle=90)
            plt.axis('equal')
            self.canvaspie.show()


            
#Uses the Win32 registry to return a iterator of serial (COM) ports existing on this computer
#got off the internet
def enumerate_serial_ports():  
    path = 'HARDWARE\\DEVICEMAP\\SERIALCOMM'
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    except WindowsError:
        raise StopIteration

    for i in itertools.count():
        try:
            val = winreg.EnumValue(key, i)
            yield (str(val[1]), str(val[0]))
        except EnvironmentError:
            break

#sets up the tkinter GUI
def main():
    root=Tk()
    root.geometry("500x500+600+100") #this is the size and position of the GUI window
    app = GUI(root)
    root.mainloop()

#If this script isn't called by another script automatically run the main method
if __name__ == '__main__':
    main()

