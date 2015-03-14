#!/usr/bin/env python
"""

 lobster - Entry/display of lobs in "real-time"
 0.1.* -> sites are static, only 1 LOB per SOI
 0.2.* -> multiple LOBs allowed (through merging)

 TODO:
      22) Give option for shapefiles ???
      62) change icons of cuts to show sender, receiver
      63) changes to sites needs to be identified as a change in file status
      66) can we add a ruler to the map i.e. click on a location, then another
          and get the distance/bearing
      67) Enable a configuration panel for map i.e. colors, markers etc
      68) Apply threshold to cuts for same callsign?
          we have to consider that an emitter may move
      69) Have a map always present option ???

 REQUIREMENTS:
  linux (not tested on windows)
  Python 2.7

 TEST POINTS:
  S LOC                                LOBS
  V 42SUA64216070    36   36  270  ---   95
  B 42SUA71356353   255  255  ---  255  202
  C 42SUA66566130   295  340  ---  295  109
  OUTCOME:          FIX CUT*  LOB  CUT  CNV
 MOVE SITES
  V 42SUA6545360394 349  92
  B 42SUA6998763986 247 180
  C 42SUA6695762994 240 133
"""

from __future__ import with_statement
import os                                         # for path
import sys                                        # restart program
import pickle                                     # load and dump
import math                                       # time conversions
import datetime as dt                             # date and time objects
import numpy as np                                # for arrays. vstack and sort
from Tix import *                                 # Tix widgets
from Tkconstants import *                         # GUI constants
from tkMessageBox import *                        # info gui
from tkFileDialog import *                        # file gui dialogs
import tkSimpleDialog                             # for modal dialogs
from PIL import Image                             # image input & support
from PIL import ImageTk                           # place these after Tix import
import matplotlib                                 # configure for matplotlib usage
matplotlib.use('TkAgg')                           # and tkinter      
from mpl_toolkits.basemap import Basemap          # basemap object
from matplotlib.figure import Figure              # figure object
from matplotlib.patches import Polygon            # polygon object
import matplotlib.backends.backend_tkagg as tkagg # tkinter backends 
import soi                                        # soi constants
from soi import SOI                               # SOI objects
from soi import Site                              # Site objects
from soi import DF                                # DF objects
from lobsterconfig import LobsterConfig           # preferences reader/writer
from landnav import convertazimuth                # convert norths
from landnav import _MGRS                         # lat,lon to mgrs conversion
from landnav import _GEOD                         # dist/direction
from landnav import terminus                      # terminus given azimuth
from landnav import dist                          # dist betw/ pts and azimuth
from landnav import validMGRS                     # valid mgrs function
from landnav import findcut                       # cut of 2 pts & lobs
from landnav import quadrant                      # quadrant of 2 pts & lobs

__name__ = 'lobster'
__license__ = 'GPL v3.0'
__version__ = '0.2.9'
__date__ = 'January 2014'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

#### GUI

# CONSTANTS
# for site entry widgets
NUM_SITES     = 4                  # allowable # of sites
SITE_TU       = 0                  # indexes into site list
SITE_NAME     = 1
SITE_LOC      = 2
SITE_LOB      = 3
SITE_BTN      = 4
SITE_LOCKED   = 5
SITE_RBTN     = 6

# for validiaty checks
CHKDATE = "0123456789-"
CHKFLOAT = "0123456789."
CHKINT = "0123456789"
CHKALNUM = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# utility functions

def l2z(l,ld):
    """ converts local time l to zulu time given a difference of ld """
    posld = abs(ld)
    tSecs = math.floor(posld)*3600 + (posld-math.floor(posld))*3600
    td = dt.timedelta(0,tSecs)
    z = l - td
    if ld < 0: z = -z
    return z

def z2l(z,ld):
    """ converts zulu time z to local time given a difference of ld """
    posld = abs(ld)
    tSecs = math.floor(posld)*3600 + (posld-math.floor(posld))*3600
    td = dt.timedelta(0,tSecs)
    l = z + td
    if ld < 0: l = -l
    return l

def restart(fpath=None):
    """ restarts the program after a preferences change """
    python = sys.executable
    args = sys.argv
    if fpath: args.append(fpath)
    os.execl(python,python,*args)

## LOBSTER GUI PANELS

class Minion(object):
    """ minion - used to maintain child window(s) """
    def __init__(self,tk,pnl,desc,fc=True):
        self.tk = tk
        self.pnl = pnl
        self.desc = desc
        self.forceClose = fc

class ChildPanel(Frame):
    """
     super class for LOBster child panels, a separate non-resizable window
     that notifying caller on closing
    """
    def __init__(self,tl,parent,ttl,ipath=None):
        """
         tl - Toplevel for this widget
         parent - the caller of this widget
         ttl - title to be displayed
        """
        Frame.__init__(self,tl)
        self.master.protocol("WM_DELETE_WINDOW",self.closeapp)
        if ipath:
            try:
                self.appicon = ImageTk.PhotoImage(Image.open(ipath))
                self.tk.call('wm','iconphoto',self.master._w,self.appicon)
            except:
                pass
        self.master.title(ttl)
        self.grid(sticky=W+N+E+S)
        self.master.resizable(0,0)
        self.parent = parent
        self._makegui()
    def closeapp(self): self.parent.childclose(self._name)

class AboutPanel(ChildPanel):
    """ Displays a simple About Dialog """
    def __init__(self,tl,parent): ChildPanel.__init__(self,tl,parent,"About LOBster")
    def _makegui(self):
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)
        self.logo = ImageTk.PhotoImage(Image.open("img/lobster-logo2.png"))
        Label(frm,image=self.logo).grid(row=0,column=0,sticky=N)
        Label(frm,text="LOBster %s" % __version__,fg="white",font=("Roman",16,'bold')).grid(row=1,column=0,sticky=N)
        Label(frm,text="LOBster is a LLVI signal editor for near\nreal-time VHF communications tracking").grid(row=2,column=0,sticky=N)
    
class HelpPanel(ChildPanel):
    """ Displays a simple Help dialog """
    def __init__(self,tl,parent):
        ChildPanel.__init__(self,tl,parent,"LOBster %s Help" % __version__,"img/help.png")
    def _makegui(self):
        """ set up the gui """
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)
        self.txtSHelp = ScrolledText(frm)
        self.txtHelp = self.txtSHelp.text
        self.txtHelp.config(width=80)
        self.txtHelp.config(height=20)
        self.txtHelp.config(wrap=WORD)
        self.txtSHelp.grid(row=0,column=0,sticky=W+N+E+S)
        try:
            fin = open('help')
            self.txtHelp.insert("1.0","LOBster %s\n\n" % __version__+fin.read())
            fin.close()
        except:
            self.txtHelp.insert("1.0","Could not find help")
        self.txtHelp.config(state=DISABLED)

class ConversionPanel(ChildPanel):
    """ displays conversion panel """
    def __init__(self,tl,parent):
        ChildPanel.__init__(self,tl,parent,"Conversion","img/tools.png")

    def convert(self):
        m = self.txtMGRS.get()
        ll = self.txtLatLon.get()
        if m and ll: showerror("Error","One field must be empty",parent=self)
        else:
            if m:
                try:
                    ll = _MGRS.toLatLon(m)
                    self.txtLatLon.insert(0,"%.3f %.3f" % (ll[0],ll[1]))
                except:
                    showerror("Error","MGRS is not valid",parent=self)
            elif ll:
                try:
                    ll = ll.split()
                    m = _MGRS.toMGRS(ll[0],ll[1])
                    self.txtMGRS.insert(0,m)
                except:
                    showerror("Error","Lat/Lon is not valid",parent=self)
    
    def clear(self):
        """ clear entries """
        self.txtMGRS.delete(0,END)
        self.txtLatLon.delete(0,END)
    
    # PRIVATE
    def _makegui(self):
        """ set up the gui """
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)
        
        # two entries one for mgrs, other for lat/lon
        frmEntries = Frame(frm)
        frmEntries.grid(row=0,column=0,sticky=W)
        Label(frmEntries,text="MGRS").grid(row=0,column=0,sticky=W)
        self.txtMGRS = Entry(frmEntries,width=15)
        self.txtMGRS.grid(row=0,column=1,sticky=W)
        Label(frmEntries,text="Lat/Lon").grid(row=0,column=2,sticky=E)
        self.txtLatLon = Entry(frmEntries,width=15)
        self.txtLatLon.grid(row=0,column=3,sticky=E)
        
        # clear button, convert button, close button
        frmBtn = Frame(frm)
        frmBtn.grid(row=1,column=0,sticky=N)
        Button(frmBtn,text="Convert",command=self.convert).grid(row=0,column=0,sticky=W)
        Button(frmBtn,text="Clear",command=self.clear).grid(row=0,column=1,sticky=W)
        Button(frmBtn,text="Close",command=self.closeapp).grid(row=0,column=2,sticky=E)

class DDPanel(ChildPanel):
    """ Displays direction/distance panel """
    def __init__(self,tl,parent):
        ChildPanel.__init__(self,tl,parent,"Distance/Direction","img/tools.png")

    def calculate(self):
        """ calc distance and direction from sp to ep """       
        sp = self.txtSP.get()
        ep = self.txtEP.get()
        if sp and ep:
            try:
                # if we get a negative azimuth, subtract it from 360
                d,a = dist(sp,ep)
                a %= 360
                self.txtAns.config(state=NORMAL)
                self.txtAns.delete(0,END)
                self.txtAns.insert(0,"%.2fm %.2f%s" % (d,a,u'\N{DEGREE SIGN}'))
                self.txtAns.config(state=DISABLED)
            except:
                showerror('Error','Enter valid MGRS points',parent=self)
        else:
            showerror('Error',"Enter MGRS for both points",parent=self)
    
    def clear(self):
        self.txtSP.delete(0,END)
        self.txtEP.delete(0,END)
        self.txtAns.config(state=NORMAL)
        self.txtAns.delete(0,END)
        self.txtAns.config(state=DISABLED)

    # PRIVATE
    def _makegui(self):
        """ set up the gui """
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)    
        
        # entry for locations, label for answer
        frmEntries = Frame(frm)
        frmEntries.grid(row=0,column=0,sticky=N)
        Label(frmEntries,text="Start").grid(row=0,column=0,sticky=W)
        self.txtSP = Entry(frmEntries,width=15)
        self.txtSP.grid(row=0,column=1,sticky=W)
        Label(frmEntries,text="End").grid(row=0,column=2,sticky=E)
        self.txtEP = Entry(frmEntries,width=15)
        self.txtEP.grid(row=0,column=3,sticky=W)
        self.txtAns = Entry(frmEntries,width=40,relief='sunken',disabledforeground="black")
        self.txtAns.grid(row=1,column=0,columnspan=4,sticky=W)
        self.txtAns.config(state=DISABLED)
                
        # clear, calculate and close 
        frmBtn = Frame(frm)
        frmBtn.grid(row=1,column=0,sticky=N)
        Button(frmBtn,text="Calculate",command=self.calculate).grid(row=0,column=0,sticky=W)
        Button(frmBtn,text="Clear",command=self.clear).grid(row=0,column=1,sticky=W)
        Button(frmBtn,text="Close",command=self.closeapp).grid(row=0,column=2,sticky=E)

class TriangulationPanel(ChildPanel):
    """
     Superclass for Triangulation utilities
     derived class must implement calculate
    """
    def __init__(self,tl,parent,ttl,nLines=1):
        self.nL = nLines # number of lines for answer widget
        ChildPanel.__init__(self,tl,parent,ttl,"img/tools.png")

    def calculate(self): pass
    def clear(self):
        self.txtLocA.delete(0,END)
        self.txtLOBA.delete(0,END)
        self.txtLocB.delete(0,END)
        self.txtLOBB.delete(0,END)
        self.txtAns.config(state=NORMAL)
        self.txtAns.delete('1.0',END)
        self.txtAns.config(state=DISABLED)
    
    def _validate(self):
        # get entries
        locA = self.txtLocA.get()
        lobA = self.txtLOBA.get()
        locB = self.txtLocB.get()
        lobB = self.txtLOBB.get()
        
        # show msg if any are empty  
        if not locA or not lobA or not locB or not lobB:
            showerror("Empty Entries","A location or LOB is missing",parent=self)
            return None,None,None,None
        
        # show msg if any are invalid
        try:
            locA = _MGRS.toLatLon(locA)
            lobA = float(lobA)
            if lobA < 0 or lobA >= 360.0: raise ValueError
        except ValueError:
            # error in lob conversion
            showerror("Invalid LOB","LOB A must be between 0 and 360",parent=self)
            return None,None,None,None
        except:
            # error in lat/lon conversion
            showerror("Invalid Location","Location A must be valid MGRS",parent=self)
            return None,None,None,None
        
        try:
            locB = _MGRS.toLatLon(locB)
            lobB = float(lobB)
            if lobB < 0 or lobB >= 360.0: raise ValueError
        except ValueError:
            # error in lob conversion
            showerror("Invalid LOB","LOB B must be between 0 and 360",parent=self)
            return None,None,None,None
        except:
            # error in lat/lon conversion
            showerror("Invalid Location","Location B must be valid MGRS",parent=self)
            return None,None,None,None
       
        # valid entries
        return locA,lobA,locB,lobB

    def _makegui(self):
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)
        
        # two rows of entries for location, lob A & B. one row for answer 
        frmEntries = Frame(frm)
        frmEntries.grid(row=0,column=0,sticky=N)
        Label(frmEntries,text="MGRS").grid(row=0,column=1,sticky=N)
        Label(frmEntries,text="TN").grid(row=0,column=3,sticky=N)
        Label(frmEntries,text="Location A").grid(row=1,column=0,sticky=W)
        self.txtLocA = Entry(frmEntries,width=15)
        self.txtLocA.grid(row=1,column=1,sticky=W)
        Label(frmEntries,text="LOB A").grid(row=1,column=2,sticky=W) 
        self.txtLOBA = Entry(frmEntries,width=7)
        self.txtLOBA.grid(row=1,column=3,sticky=W)
        Label(frmEntries,text="Location B").grid(row=2,column=0,sticky=W)
        self.txtLocB = Entry(frmEntries,width=15)
        self.txtLocB.grid(row=2,column=1,sticky=W)
        Label(frmEntries,text="LOB B").grid(row=2,column=2,sticky=W) 
        self.txtLOBB = Entry(frmEntries,width=7)
        self.txtLOBB.grid(row=2,column=3,sticky=W)        
        self.txtAns = Text(frmEntries,width=42,height=self.nL,relief='sunken',disabledforeground="black")
        self.txtAns.grid(row=3,column=0,columnspan=4,sticky=W)
        self.txtAns.config(background="gray")
        self.txtAns.config(cursor="circle")
        self.txtAns.config(state=DISABLED)
        
        # clear, calculate and close 
        frmBtn = Frame(frm)
        frmBtn.grid(row=1,column=0,sticky=N)
        Button(frmBtn,text="Calculate",command=self.calculate).grid(row=0,column=0,sticky=W)
        Button(frmBtn,text="Clear",command=self.clear).grid(row=0,column=1,sticky=W)
        Button(frmBtn,text="Close",command=self.closeapp).grid(row=0,column=2,sticky=E)

    def _displayanswer(self,ans):
        self.txtAns.config(state=NORMAL)
        self.txtAns.delete('1.0',END)
        self.txtAns.insert(END,ans)
        self.txtAns.config(state=DISABLED)

class CutPanel(TriangulationPanel):
    """ displays find fix panel """
    def __init__(self,tl,parent):
        TriangulationPanel.__init__(self,tl,parent,"Find Cut")

    def calculate(self):
        """ calculate cut from 2 pts """
        # if valid entries, find the cut, otherwise, do nothing
        (locA,lobA,locB,lobB) = self._validate()
        if locA:
            ans = findcut(locA,lobA,locB,lobB)
            if type(ans) == type((0,1)):
                # answer is a tuple convert cut to mgrs & get distances
                dest = _MGRS.toMGRS(ans[0],ans[1])
                da = _GEOD.inv(locA[1],locA[0],ans[1],ans[0])[2]
                db = _GEOD.inv(locB[1],locB[0],ans[1],ans[0])[2]
                res = "%s dA: %.1fm dB: %.1fm" % (dest,da,db)
            else:
                # no cut
                res = "No Cut"
        
        # write the answer
        self._displayanswer(res)

class QuadrantPanel(TriangulationPanel):
    """ Displays find quadrant panel """
    def __init__(self,tl,parent):
        TriangulationPanel.__init__(self,tl,parent,"Find Quadrant (3%s Error)" % u'\N{DEGREE SIGN}',2)

    def calculate(self):
        """ calculate cut from 2 pts """
        # if valid entries, find the cut, otherwise, do nothing
        (locA,lobA,locB,lobB) = self._validate()
        if locA:
            [q1,q2,q3,q4] = quadrant(locA,lobA,locB,lobB)
            if type(q1) == type(q2) == type(q3) == type(q4) == type((0,1)):
                # found an answer
                res = "%s %s\n%s %s" % (_MGRS.toMGRS(q1[0],q1[1]),\
                                       _MGRS.toMGRS(q2[0],q2[1]),\
                                       _MGRS.toMGRS(q3[0],q3[1]),\
                                       _MGRS.toMGRS(q4[0],q4[1]))
            else:
                # no good answer
                res = "No Cut"
        
        # write the answer
        self._displayanswer(res)

class ExportCSVPanel(ChildPanel):
    """ Displays export to csv panel """
    def __init__(self,tl,parent,sois,sites):
        self._sois = sois
        self._sites = sites
        ChildPanel.__init__(self,tl,parent,"Export Green 6","img/export.png")

# CALLBACKS
    
    def export(self):
        # get preferences, type
        site = "All"
        if self.eType.get() == 0: site = self.svar.get()
        north = self.nvar.get()
        north = north.lower()
        time = self.tvar.get()
        time = time.lower()
        n = dt.datetime.utcnow()
        fname = n.date().strftime("%Y-%m-%d")+"_"+n.time().strftime("%H%M")+"_%s" % site
        fpath = asksaveasfilename(title='Export Green 6',\
                                  initialfile="%s.csv" % fname,\
                                  filetypes=[('CSV Files','*.csv')])
        if fpath:
            try:
                # if successful, close the dialog
                fout = open(fpath,'w')
                if site == "All":
                    sites = self._sites
                else:
                    sites = [site]
                recs = self._writesois(fout,north,time,sites)
                fout.close()
                showinfo("Exported","Wrote %d SOIs to %s" % (recs,os.path.split(fpath)[1]))
                self.parent.childclose(self._name)
            except Exception, e:
                fout.close()
                showerror("Error","Error writing %s" % os.path.split(fpath)[1])
        else:
            # do nothing
            return

    def cbRdoType(self,val):
        """ enables/disables site dropdown as necessary """
        if val == 0:
            self.optSites.configure(state=NORMAL)
        else:
            self.optSites.configure(state=DISABLED)
                
# PRIVATE

    def _makegui(self):
        """ set up the gui """
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)
        
        # 4 frames - export type, export preferences, file to export to, buttons
        frmType = Frame(frm,borderwidth=1,relief='sunken')
        frmType.grid(row=0,column=0,sticky=W)
        self.eType = IntVar(self)
        self.rdoTypeSingle = Radiobutton(frmType,text="Single",variable=self.eType,\
                                         value=0,command=lambda:self.cbRdoType(0))
        self.rdoTypeSingle.grid(row=0,column=0,sticky=W)
        self.rdoTypeAll = Radiobutton(frmType,text="All",variable=self.eType,\
                                      value=1,command=lambda:self.cbRdoType(1))
        self.rdoTypeAll.grid(row=1,column=0,sticky=W)
        self.svar = StringVar(self)
        self.svar.set(self._sites[0])
        self.optSites = Tkinter.OptionMenu(frmType,self.svar,*self._sites)
        self.optSites.grid(row=0,column=1,sticky=E)
        
        frmPref = Frame(frm,borderwidth=1,relief='sunken')
        frmPref.grid(row=1,column=0,sticky=W)
        lblNorth = Label(frmPref,text="North:").grid(row=0,column=0,sticky=W)
        norths = ["True","Grid","Magnetic"]
        self.nvar = StringVar(self)
        self.nvar.set(norths[0])
        self.optNorths = Tkinter.OptionMenu(frmPref,self.nvar,*norths)
        self.optNorths.grid(row=0,column=1,sticky=E)
        Label(frmPref,text="DTG:").grid(row=1,column=0,sticky=W)
        times = ["Zulu","Local"]
        self.tvar = StringVar(self)
        self.tvar.set(times[0])
        self.optTimes = Tkinter.OptionMenu(frmPref,self.tvar,*times)
        self.optTimes.grid(row=1,column=1,sticky=E)

        frmBtn = Frame(frm)
        frmBtn.grid(row=2,column=0,sticky=W)
        Button(frmBtn,text="Export",command=self.export).grid(row=0,column=0,sticky=W)
        Button(frmBtn,text="Close",command=self.closeapp).grid(row=0,column=1,sticky=E)

    def _writesois(self,f,n,t,ss):
        """
         writes sois to f in desired north=n and time=t. Only writes those 
         sites in ss and excludes any convos
        """
        # write the header
        G6_HEADER = ["NUM","SITE","LOCATION","TIME UP","RF","LOB","CALLSIGNS","GIST","OP NOTE","GEOLOCATION"]
        hdr = ""
        for h in G6_HEADER[:-1]: hdr += "%s," % h
        hdr += "%s\n" % G6_HEADER[len(G6_HEADER)-1]
        f.write(hdr)
        
        recNum = 0
        # iterate each soi  
        for sid in self._sois:
            soi = self._sois[sid]
            try:
                soi.dtg
            except AttributeError:
                # no dtg this is a convo
                pass
            else:
                for ssid in soi.pri:
                    # only write if it is in specified sites list
                    if ssid in ss:
                        recNum += 1
                        f.write("%d," % recNum)  # NUM    
                        f.write("%s," % ssid) # SITE
                        f.write("%s," % soi.sites[ssid].location) # LOCATION
                        tu = soi.dtg
                        if t == "local": 
                            tu = z2l(tu,self.parent.config.ui['z2l'])
                            tu = tu.strftime("%d%H%ML%b%Y").upper()
                        else:
                            tu = tu = tu.strftime("%d%H%ML%b%Y").upper()
                        f.write("%s," % tu) # TIME UP   
                        f.write("%.3f," % soi.getrf()) # RF
                        lob = soi.sites[ssid].lob
                        if n != "true": lob = convertazimuth("true",n,lob,self.parent.config.declination) 
                        f.write("%.1f," % lob) # LOB
                        css = soi.getuniquecallsigns()
                        callsigns = ""
                        if css:
                            for cs in css[:-1]: callsigns += "%s " % cs
                            callsigns += "%s" % css[len(css)-1]
                        f.write("%s," % callsigns) # CALLSIGNS
                        f.write("%s," % self._cleantext(soi.gist)) # GIST
                        f.write("%s," % self._cleantext(soi.opnote)) # OP NOTE
                        f.write("%s\n" % soi.df.status) # GEOLOCATION
        return recNum        
        
    def _cleantext(self,text):
        """ cleans text for csv, removes non-printable characters and commas """
        return "".join([ch for ch in text if 31 < ord(ch) < 126 and ord(ch) != 44])
         
class PreferencesPanel(ChildPanel):
    """
     Displays configuration options for modifying
    """
    def __init__(self,tl,parent,config):
        ChildPanel.__init__(self,tl,parent,"Preferences","img/wrench.png")
        self._initialize()
    
# CALLBACKS
    
    def save(self):
        # validate
        # declination
        decl = self.dvar.get().lower()
        try:
            g2m = float(self.txtG2M.get())
            g2t = float(self.txtG2T.get())
        except:
            showerror('Invalid','G-M and G-T must be numeric')
            return
        if not (decl == 'westerly' or decl == 'easterly'):
            showerror('Invalid','Direction must be westerly or easterly')
            return
        if g2m < 0 or g2m >= 360:
            showerror('Invalid','G-M must be between 0 and 360')
            return
        if g2t < 0 or g2t >= 360:
            showerror('Invalid','G-T must be between 0 and 360')
            return
            
        # ellipse - for now only allow WGS84
        ellipse = self.txtEllipse.get()
        ellipse = ellipse.upper()
        try:
            cutt = int(self.txtCutt.get())
        except:
            showerror('Invalid','Cut Threshold must be numeric')
            return
        if ellipse != "WGS84":
            showerror('Invalid','Currently on WGS84 allowed')
            ellipse = "WGS84"
        
        # ui
        north = self.nvar.get().lower()
        dtime = self.tvar.get().lower()

        try:
            z2l = float(self.txtZ2L.get())
        except:
            showerror('Invalid',"Time Diff must be numeric")
            return
        if not (north == "true" or north == "grid" or north == "magnetic"):
            showerror('Invalid',"North must be true,gird or magnetic")
            return
        if not (dtime == "local" or dtime == "zulu"):
            showerror('Invalid',"Display time must be local or zulu")
            return
        
        # everything checks out, write to conf file
        lc = LobsterConfig()
        lc.declination = {'decl':decl,'g2m':g2m,'g2t':g2t}
        lc.geo = {'ellipse':ellipse,'cutt':cutt}
        lc.ui = {'azimuth':north,'z2l':z2l,'dtime':dtime}
        try:
            lc.write('lobster.conf')
        except:
            showerror('Error','Failed to write lobster.conf')
        else:
            self.parent.changeprefs()
    
    def _makegui(self):
        """ make the gui widgets """
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)
        
        # declination
        frmDecl = Frame(frm,borderwidth=1,relief='sunken')
        frmDecl.grid(row=0,column=0,sticky=W)
        Label(frmDecl,text="Direction:        ").grid(row=0,column=0,sticky=E)
        dirs = ["Easterly","Westerly"]
        self.dvar = StringVar(self)
        self.dvar.set(dirs[0])
        self.optDirections = Tkinter.OptionMenu(frmDecl,self.dvar,*dirs)
        self.optDirections.grid(row=0,column=1,sticky=E)
        Label(frmDecl,text="G-M:").grid(row=1,column=0,sticky=W)
        self.txtG2M = Entry(frmDecl,width=4)
        self.txtG2M.grid(row=1,column=1,sticky=E)
        Label(frmDecl,text="G-T:").grid(row=2,column=0,sticky=W)
        self.txtG2T = Entry(frmDecl,width=4)
        self.txtG2T.grid(row=2,column=1,sticky=E)
        
        # geo (for now, hardcode datum & disable changes)
        frmGeo = Frame(frm,borderwidth=1,relief='sunken')
        frmGeo.grid(row=1,column=0,sticky=W)
        Label(frmGeo,text="Datum:").grid(row=0,column=0,sticky=W)
        self.txtEllipse = Entry(frmGeo,width=7)
        self.txtEllipse.grid(row=0,column=1,sticky=W)
        self.txtEllipse.insert(0,"WGS84")
        self.txtEllipse.config(state=DISABLED)
        Label(frmGeo,text="Cut Threshold:   ").grid(row=1,column=0,sticky=W)
        self.txtCutt = Entry(frmGeo,width=4)
        self.txtCutt.grid(row=1,column=1,sticky=E)
        
        # ui
        frmUI = Frame(frm,borderwidth=1,relief='sunken')
        frmUI.grid(row=2,column=0,sticky=W)
        Label(frmUI,text="North:").grid(row=0,column=0,sticky=W)
        norths = ["True","Grid","Magnetic"]
        self.nvar = StringVar(self)
        self.nvar.set(norths[0])
        self.optNorths = Tkinter.OptionMenu(frmUI,self.nvar,*norths)
        self.optNorths.grid(row=0,column=1,sticky=E)
        Label(frmUI,text="Local Time Diff:").grid(row=1,column=0,sticky=W)
        self.txtZ2L = Entry(frmUI,width=4)
        self.txtZ2L.grid(row=1,column=1,sticky=E)
        Label(frmUI,text="Display Time:").grid(row=2,column=0,sticky=W)
        times = ["Zulu","Local"]
        self.tvar = StringVar(self)
        self.tvar.set(times[0])
        self.optTimes = Tkinter.OptionMenu(frmUI,self.tvar,*times)
        self.optTimes.grid(row=2,column=1,sticky=E)
        
        # save,close buttons
        frmBtn = Frame(frm)
        frmBtn.grid(row=3,column=0,sticky=N)
        Button(frmBtn,text="Save",command=self.save).grid(row=0,column=0,sticky=W)
        Button(frmBtn,text="Close",command=self.closeapp).grid(row=0,column=1,sticky=W)
        
    def _initialize(self):
        """ reads in .conf file and initializes widgets """
        lc = LobsterConfig()   
        try:     
            lc.read('lobster.conf')
            # declination
            self.dvar.set(lc.declination['decl'].title())
            self.txtG2M.insert(0,lc.declination['g2m'])
            self.txtG2T.insert(0,lc.declination['g2t'])
       
            # geo
            self.txtEllipse.insert(0,lc.geo['ellipse'])
            self.txtCutt.insert(0,lc.geo['cutt'])
            
            # ui
            self.nvar.set(lc.ui['azimuth'].title())
            self.txtZ2L.insert(0,lc.ui['z2l'])
            self.tvar.set(lc.ui['dtime'].title())
        except Exception, e:
            showerror('Corrupt File','lobster.conf has errors %s' % e)

#### PICKQUADRANT DIALOG FOR MAP PANEL

class LOBErrorPanel(tkSimpleDialog.Dialog):
    """
     displays sites for user to select for error lob drawing, use 
     tkSimpleDialog.Dialog because we want this to be modal
    """
    def __init__(self,parent,sites):
        self.sites = sites
        tkSimpleDialog.Dialog.__init__(self,parent,title="Map Quadrant")
    def body(self,master):
        # radio button set of cuts
        self.v = IntVar()
        self.v.set(0)
        
        i = 0
        self.rbs = []
        for s in self.sites:
            rb = Radiobutton(master,text="%s" % s,value=i,variable=self.v)
            rb.grid(row=i,column=0,sticky=W)
            self.rbs.append(rb)
            i+=1
        
        # entry for degrees of error
        Label(master, text="Error: (1 to 10)").grid(row=i,column=0,sticky=W)
        self.txtDegree = Entry(master,width=3)
        self.txtDegree.grid(row=i,column=1,sticky=W)
        self.txtDegree.insert(0,'3')
        
        # colors
        Label(master, text="Error Color").grid(row=i+1,sticky=W)
        self.colors = ['black','green','red','blue','yellow','magenta','coral','orange']
        self.cvar = StringVar(self)
        self.cvar.set(self.colors[0])
        self.optColors = Tkinter.OptionMenu(master,self.cvar,*self.colors)
        self.optColors.grid(row=i+1,column=1,sticky=W)
        
        return self.rbs[0]        

    def validate(self):
        """ make sure entered data is valid """    
        try:
            d = int(self.txtDegree.get())
        except ValueError:
            showerror("Invalid Entry","Error Degree must be between 1 and 10",parent=self)
            return 0
        else:
            if 0 < d < 11: return 1
            else:
                showerror("Invalid Entry","Error Degree must be between 1 and 10",parent=self)    
        
    def apply(self):
        """ pass back selected cut and error degree as a tuple """
        self.result = (self.sites[self.v.get()],int(self.txtDegree.get()),self.cvar.get())

#### Private NavigationToolbar subclass
class _NavBar(tkagg.NavigationToolbar2TkAgg):
    """ Customizes matplotlib NavigationToolbar """
    def __init__(self,control,canvas,window):
        self.control = control
        self.canvas=canvas
        self.window=window
        self._idle=True
        
        # we override toolitems before initializing IOT to remove buttons 
        # we don't want and add buttons - this is a lot easier than rewriting 
        # _init_toolbar
        # NOTE: any button images are saved in 
        # /usr/local/lib/python2.7/dist-packages/matplotlib/mpl-data/images/
        # TODO is there a way to work around this?
        self.toolitems = (('Home', 'Reset original view', 'home', 'home'),\
                          ('Back', 'Back to  previous view', 'back', 'back'),\
                          ('Forward', 'Forward to next view', 'forward', 'forward'),\
                          ('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'),\
                          ('Separator','','separator','do_nothing'),\
                          ('Lob Error','Draw LOBs with errors','quadrant','loberror'),\
                          ('Clear','Clear Error LOBs','erase','clear'),\
                          ('Annotate','Annotate','labels','label'),\
                          ('Separator','','separator','do_nothing'),\
                          ('Save', 'Save the figure', 'filesave', 'save_figure'))
        tkagg.NavigationToolbar2.__init__(self,canvas)

    def do_nothing(self): pass

    def loberror(self):
        """ show quadrant around 2 selected lobs """
        self.control.loberror()

    def clear(self):
        """ clear all quadrants """
        self.control.clearloberrors()

    def label(self):
        """ show labels """
        self.control.annotate()
    
    def set_message(self,s):
        """ override to show mgrs rather than x,y """
        # if s has the format x=<xcoord> y=ycoord and it's not a 
        # a zoom rect, change to show mgrs otherwise just show s
        if "x=" in s and "y=" in s:
            if s.startswith('zoom rect,'): s = s.replace('zoom rect,','')
            
            # remove white space using split which returns a list with
            # x=<xcoord> and y=<ycoord>. split each of these on '=' and convert
            # to float to get the numeric x and y coords
            coords=s.split() # remove white space, returns a list with x and y
            x = float(coords[0].split('=')[1])
            y = float(coords[1].split('=')[1])
            s = self.control._statusbar((x,y))    
        self.message.set(s)
  
class MapPanel(ChildPanel):
    """
     Displays SOI on a simple map
    """
    def __init__(self,tl,parent,key,soi):
        self.key = key # key of the soi
        self.soi = soi # the soi data
        self.qs = []   # list of quandrants drawn
        self.ls = []   # list of text labels drawn
        ChildPanel.__init__(self,tl,parent,"Triangulation SOI %d" % key,"img/globe.png")

    # CALLBACKS
    
    def loberror(self):
        """ displays lob errors for selected sites """
        # show the lob error panel and get the user selected        
        # d.result is a tuple (site,err,color)
        d = LOBErrorPanel(self,self.soi.pri)
        if d.result is None: return
        loc = self.soi.sites[d.result[0]].location
        lob = self.soi.sites[d.result[0]].lob
        err = d.result[1]
        color = d.result[2]
        self._drawloberror(loc,lob,err,color)

    def clearloberrors(self):
        """ removes any drawn loberrors """
        for q in self.qs: q.remove()
        self.canvas.show()
        self.qs = []
  
    def annotate(self):
        """ labels site(s), degrees of LOB(s), cut(s) """
        if not self.ls:
            for l in self.ptLabels:
                self.ls.append(self.ax.text(l[0]+1,l[1]+1,l[2]))
        else:
            for l in self.ls: l.remove()
            self.ls = []
        self.canvas.show()
    
    # PRIVATE
    def _makegui(self):
        """ 
         make gui, embeds a matplotlib figure 
         NOTE EPSG 4326 is WGS84
        """
        # sites will be colored circles with a white cross & cuts will be a 
        # colored squares with a white star
        # TODO: how to make index reflect these markers
        #       10000 may not be enought
        lobDist = 10000                                     
        msize = 7
        sitecolors = ['g','r','b','y'] 
        cutcolors = ['k','g','r','b','y','m','c','orange']
        
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)
        
        # make a figure & get the axes
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111,title="DTG: %s RF: %.3f" % (self.soi.getdtg(),self.soi.getrf()))
        
        # make a basemap using axes from above centered around the primary site 
        # of the soi. we want the map to contain all sites and lobs but zoomed in 
        # enough to be relevant without manual zooming. we do this by setting the 
        # width and height to 1, the map will 'grow' to fit the gridlines
        primary = self.soi.sites[self.soi.pri[0]].location
        (lat,lon) = _MGRS.toLatLon(primary)
        self.base = Basemap(projection='tmerc',\
                            lat_0=lat,\
                            lon_0=lon,\
                            resolution='h',\
                            area_thresh=0.1,\
                            width=1,\
                            height=1,\
                            ax=self.ax,\
                            suppress_ticks=False)
        
        # save for labeling, each is a tuple (x,y,lbl)
        self.ptLabels = []
        
        # plot sites and lobs - maintain list of all points for gridlines
        i = 0
        locs = []
        for site in self.soi.pri:
            # get the next site, it's location. convert to lat/lon & project
            s = self.soi.sites[site]
            (lat,lon) = _MGRS.toLatLon(s.location)
            x,y = self.base(lon,lat)
            self.ptLabels.append((x,y,s.name))
            
            # draw at projection with corresponding color and white cross, add label for index
            self.base.plot(x,y,sitecolors[i]+'o',markersize=msize,\
                           label="%s: %d%s" % (s.name,s.lob,u'\N{DEGREE SIGN}'))
            self.base.plot(x,y,'w+',markersize=msize)
            
            # get end pt of site lobDist away on site's azimuth & project onto map
            (lat1,lon1,mgrs1,baz) = terminus(s.location,s.lob,lobDist)
            x1,y1 = self.base(lon1,lat1)
            self.base.plot([x,x1],[y,y1],sitecolors[i])
            self.ptLabels.append((x1,y1,"%d%s" % (s.lob,u'\N{DEGREE SIGN}')))
            
            # store site and terminus
            locs.extend([s.location,mgrs1])
            
            # incr sitecolor index
            i += 1       
                        
        # plot any fix/cut(s)
        if self.soi.df.state == soi.DF_FIX:
            # a fix, plot location of the first cut
            (lat,lon) = _MGRS.toLatLon(self.soi.df.fix)
            x,y = self.base(lon,lat)
            self.ptLabels.append((x,y,self.soi.df.cuts[0][soi.DF_CUT_X]))
            self.base.plot(x,y,cutcolors[0]+'s',markersize=msize)
            self.base.plot(x,y,'w*',markersize=msize)
        elif self.soi.df.state >= soi.DF_CUT:
            # multiple cuts, plot all
            i = 0
            for cut in self.soi.df.cuts:
                # for each cut, get location, convert to lat,lon and project onto map
                (lat,lon) = _MGRS.toLatLon(cut[soi.DF_CUT_X])
                x,y = self.base(lon,lat)
                self.ptLabels.append((x,y,cut[soi.DF_CUT_X]))
                self.base.plot(x,y,cutcolors[i]+'s',markersize=msize)
                self.base.plot(x,y,'w*',markersize=msize)
                
                # incr the cutcolor index
                i += 1

        """
        # is there a polygon to fill with the cuts?
        # TODO some polygons (i.e. soi 1) do not fill in the polygon completely
        # 
        if len(self.soi.df.cuts) >= 3:
            lons = []
            lats = []
            for cut in self.soi.df.cuts:
                (lat,lon) = _MGRS.toLatLon(cut[6]) 
                lats.append(lat)
                lons.append(lon)
                #x,y = self.base(lon,lat)
                #self.base.plot(x,y,'r+',markersize=10)
            xs,ys = self.base(lons,lats)
            xy = np.vstack([xs,ys]).T   
            p = Polygon(xy,closed=True,facecolor='black',linewidth=1,alpha=0.4)        
            self.fig.gca().add_patch(p)              
        """
                
        # draw mgrs gridlines
        self._drawgridlines(locs)
        
        # use a FigureCanvas and custom navigation toolbar
        self.canvas = tkagg.FigureCanvasTkAgg(self.fig,master=frm)
        tbar = _NavBar(self,self.canvas,frm)
        
        self.ax.legend(loc=2,borderaxespad=0.2,numpoints=1)
        
        # show the canvas and pack it
        self.canvas.show()
        self.canvas.get_tk_widget().pack(side=TOP,fill=BOTH,expand=1)

    def _drawgridlines(self,ls):
        """
         draws north and east gridlines
          ls -> list of all point locations
         1) Have to set suppress_ticks in Basemap initialization to False.
         2) We need to keep the x,y values which are somehow tied to major ticks
            for converting to mgrs on mouseover but don't want these shown on
            the map. We do this by ax.set_[x|y]ticks([])
         3) use the minor ticks to for grid labels
         4) the gridlines are not perfectly parallel to the figure boundary
            can't use grid() or horizontal, vertical lines. 
         5) IOT to label the grid lines we use the minor ticks, which makes 
            the left/bottom edge of the map somewhat unsightly and they don't
            match the gridlines when zoomed in
         TODO:
           1) cannot handle situations where map crosses more than one zone
              horizontally or vertically - add a check for this
        """
        # NOTE: cannot handle different grid zone designators
        (ll,ur) = self._gridcorners(ls)
        (es,ns) = self._gridings(ll,ur)
        gzd = ll[0:3] 
        
        # sanity check - if the grid zone designators are different
        if ll[0:3] != ur[0:3]:
            showinfo("Error","Multiple GZDs, will not draw gridlines",parent=self)
            return
        
        # draw eastings from first northing to last
        xs = []
        prevZ = es[0][0]
        for e in es:
            # for each easting, plot a line from the first northing to the last
            (lat,lon) = _MGRS.toLatLon("%s%s%s%s%s" % (gzd,e[0],ns[0][0],e[1],ns[0][1]))
            (lat1,lon1) = _MGRS.toLatLon("%s%s%s%s%s" % (gzd,e[0],ns[len(ns)-1][0],e[1],ns[len(ns)-1][1]))
            x,y = self.base(lon,lat)
            x1,y1 = self.base(lon1,lat1)
            if prevZ == e[0]:
                gColor = "#993300"
            else:
                gColor = "black"
            prevZ = e[0]
            self.base.plot([x,x1],[y,y1],linestyle='-',color=gColor)
            xs.append(x)
        # tick labels, disable major & use minor using the 2digit as tick marks    
        # TODO: label grid changes i.e. instead of 00, use TA/UA ???
        self.ax.set_xticks([])
        self.ax.set_xticks(xs,minor=True)
        self.ax.set_xticklabels([e[1] for e in es],minor=True)
        
        # draw northings from first easting to last
        ys = []
        prevZ = ns[0][0]
        for n in ns:
            # for each northing, plot a line from the first easting to the last
            (lat,lon) = _MGRS.toLatLon("%s%s%s%s%s" % (gzd,es[0][0],n[0],es[0][1],n[1]))
            (lat1,lon1) = _MGRS.toLatLon("%s%s%s%s%s" % (gzd,es[len(es)-1][0],n[0],es[len(es)-1][1],n[1]))
            x,y = self.base(lon,lat)
            x1,y1 = self.base(lon1,lat1)
            if prevZ == n[0]:
                gColor = "#993300"
            else:
                gColor = "black"
            prevZ = n[0]
            self.base.plot([x,x1],[y,y1],linestyle='-',color=gColor)
            ys.append(y)
        # tick labels, disable major & use minor using the 2digit as tick marks   
        self.ax.set_yticks(ys,minor=True)
        self.ax.set_yticklabels([n[1] for n in ns],minor=True)
        self.ax.set_yticks([])        
    
    def _gridcorners(self,gs):
        """
         Given gs, a list of mgrs locations returns the mgrs location at the 
         lower left and upper right corners such that each location in gs is 
         encompassed
        """
        # make the first point in the list the min/max
        (lat,lon) = _MGRS.toLatLon(gs[0])
        w=e = lon
        s=n = lat
    
        # iterate list of points excluding the first saving min, max lat and lon
        for g in gs[1:len(gs)]:
            (lat,lon) = _MGRS.toLatLon(g)
            w=min(lon,w)
            e=max(lon,e)
            s=min(lat,s)
            n=max(lat,n)
    
        # convert the far south and far west as lower left and the far north and 
        # far east as upper right
        ll = _MGRS.toMGRS(s,w)
        ur = _MGRS.toMGRS(n,e)
        
        return ll,ur

    def _gridings(self,ll,ur):
        """
         given ll, a lower left mgrs location and ur, an upper right mgrs location
         returns the tuple es = eastings, ns = northings such that:
          each es is a pair (L=east to west band,DD=2 digit location)
          each ns is a pair (L=south to north band,DD=2 digit location)
        """
        # inc to add/subtract from extremes if we have a 1000m wide/high map
        eInc = 0
        nInc = 0
        if abs(int(ll[5:7])-int(ur[5:7])) % 100 <= 1: eInc += 2
        if abs(int(ll[10:12])-int(ur[10:12])) % 100 <= 1: nInc += 2
        
        # eastings    
        es = []
        curL = ll[3]
        curE = ll[5:7] 
        next = self._firsting(curL,curE,eInc)
        stop = self._lasting(ur[3],ur[5:7],eInc)
        while next != stop:
            # append next to list of eastings
            es.append(next)
            
            # calculate the next easting
            nextE = (int(next[1]) + 1) % 100
            if nextE == 0:
                # increase the letter designator skip 'O' and 'I'
                curL = chr(ord(curL)+1)
                if curL == '0' or curL == 'I':
                    curL = chr(ord(curL)+1)
            nextE = str(nextE)
            if len(nextE) == 1: nextE = "0" + nextE
            next = [curL,nextE]
        
        # northings
        ns = []
        curL = ll[4]
        curN = ll[10:12]
        next = self._firsting(curL,curN,nInc)
        stop = self._lasting(ur[4],ur[10:12],nInc)
        while next != stop:
            # append next to list of northings
            ns.append(next)
            
            # calculate the next northings
            nextN = (int(next[1]) + 1) % 100
            if nextN == 0:
                # increase the letter designator skip 'O' and 'I'
                curL = chr(ord(curL)+1)
                if curL == '0' or curL == 'I':
                    curL = chr(ord(curL)+1)
            nextN = str(nextN)
            if len(nextN) == 1: nextN = "0" + nextN
            next = [curL,nextN]

        return es,ns

    def _firsting(self,l,d,i):
        """ decrements i and ensures a valid first 'ing """
        newd = (int(d) - i) % 100
        newl = l
        if newd > int(d):
            newl = chr(ord(newl)-1)
            if newl == '0' or newl == 'I':
                newl = chr(ord(newl)-1)
        newd = str(newd)
        if len(newd) == 1: newd = "0" + newd
        return [newl,newd]    

    def _lasting(self,l,d,i):
        """ increments i and adds 2 to ensure extremes of map are drawn """
        newd = (int(d) + (i +2)) % 100
        newl = l
        if newd < int(d):
            newl = chr(ord(newl)+1)
            if newl == 'O' or newl == 'I':
                newl = chr(ord(newl)+1)
        newd = str(newd)
        if len(newd) == 1: newd = 'O' + newd
        return [newl,newd]

    def _drawloberror(self,loc,lob,err,color):
        """ draws an error around the lob """
        # TODO figure a way to set lobdist to 10000
        # get lat/lon and +/- lobs
        (lat,lon) = _MGRS.toLatLon(loc)
        mB = (lob - err) % 360
        pB = (lob + err) % 360
        
        # TODO: 
        # draw edges as dashed lines, in same color as polygon
        (mLat,mLon,mmgrs,mbaz) = terminus(loc,mB,10000)
        mX,mY = self.base(mLon,mLat)
        (pLat,pLon,pmgrs,pbaz) = terminus(loc,pB,10000)
        
        # project and stack
        xs,ys = self.base([lon,mLon,pLon],[lat,mLat,pLat])
        xy = np.vstack([xs,ys]).T
        
        # we have three points now
        p = Polygon(xy,closed=True,facecolor=color,linewidth=0,alpha=0.4)
        self.fig.gca().add_patch(p)
        self.qs.append(p)
        self.canvas.show()
        
    def _statusbar(self,cs):
        """ 
         converts the (x,y) tuple coords to mgrs format 
         private fct used by _NavBar for mouseover
        """
        lon,lat = self.base(cs[0],cs[1],inverse=True)
        m = _MGRS.toMGRS(lat,lon)
        retval = "%s (lat=%f lon=%f)" % (m,lat,lon)
        return retval

class ConvoMapPanel(MapPanel):
    """
     Extends MapPanel for drawing multiple SOIS
     Have to be cognizant of several things:
          1) not all sites may be present in every SOI
          2) site locations may have moved
    """
    def __init__(self,tl,parent,key,cnv):
        """ we don't want MapPanel's initialization """
        self.key = key # parent's internal data key
        self.cnv = cnv # the convo
        self.qs = []   # list of quadrants drawn
        self.ls = []   # list of labels annotated
        ChildPanel.__init__(self,tl,parent,"Triangulation Convo %d" % key,"img/globe.png")

#### CALLBACKS

    def loberror(self):
        """ overrides MapPanel lob error fct """
        # show the lob error panel and get the user selected        
        sites = []
        for o in self.cnv.order:
            for site in self.parent._sois[self.cnv.keys[o]].sites:
                if not site in sites:
                    sites.append(site)
        
        # returns tupel site,err,color
        d = LOBErrorPanel(self,sites)
        if d.result is None: return
        
        # draw lob for each soi that site is in
        for o in self.cnv.order:
            s = self.parent._sois[self.cnv.keys[o]]
            if s.sites.has_key(d.result[0]):
                self._drawloberror(s.sites[d.result[0]].location,\
                                   s.sites[d.result[0]].lob,\
                                   d.result[1],\
                                   d.result[2])
        
#### PRIVATE FCTS

    def _makegui(self):
        """ defines the map drawing for a Convo """
        # sites will be colored circles with a white cross & cuts will be a 
        # colored squares with a white star
        # TODO: how to make index reflect these markers
        #       10000 may not be enough
        guiconfig = {'lobDist':10000,\
                     'msize':7,\
                     'cutcolors':['k','g','r','b','y','m','c','orange']}
        
        # get sender and responders. identify if static or moved during collect
        snd = self.parent._sois[self.cnv.sender]
        rcvs = []
        for o in self.cnv.order[1:]: # skip the first i.e. the sender
            rcvs.append(self.parent._sois[self.cnv.keys[o]])
        
        # structs for data keeping
        sitecolors = ['g','r','b','y'] # allowed site colors
        allsites = {}                  # dict of all sites
        indexed = []                   # list of any sites that have been added to the index
        self.ptLabels = []             # list of annotation labels as a tuple (x,y,lbl)
        
        # make a dict of sites, colors and locations starting with sender
        c = 0
        for site in snd.sites.keys():
            allsites[site] = {'color':sitecolors[c],\
                              'locations':[snd.sites[site].location]}
            c += 1
        
        # add any sites that weren't in sender, all locations if any sites
        # have moved during collection
        for rcv in rcvs:
            for site in rcv.sites.keys():
                if not allsites.has_key(site):
                    allsites[site] = {'color':sitecolors[c],\
                                      'locations':[rcv.sites[site].location]}
                    c += 1
                else:
                    if not rcv.sites[site].location in allsites[site]['locations']:
                        allsites[site]['locations'].append(rcv.sites[site].location)
        
        # main frame
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)
        
        # make a figure & get the axes
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111,title="DTG: %s RF: %.3f" % (snd.getdtg(),snd.getrf()))        
        
        # make a basemap using axes from above. Center around the sender, primary
        # site. Set the width and height to 1 (map will grow after adding gridlines)
        primary = snd.sites[snd.pri[0]].location
        (lat,lon) = _MGRS.toLatLon(primary)
        self.base = Basemap(projection='tmerc',\
                            lat_0=lat,\
                            lon_0=lon,\
                            resolution='h',\
                            area_thresh=0.1,\
                            width=1,\
                            height=1,\
                            ax=self.ax,\
                            suppress_ticks=False)
        
        # plot the sender, then receivers in order of time
        locs = []
        locs.extend(self._plotsoi(snd,allsites,indexed,guiconfig,0))
        
        current = 1
        for rcv in rcvs:
            locs.extend(self._plotsoi(rcv,allsites,indexed,guiconfig,current))
            current += 1
        
        # draw the gridlines
        self._drawgridlines(locs)
        
        # use a FigureCanvas and custom navigation toolbar
        self.canvas = tkagg.FigureCanvasTkAgg(self.fig,master=frm)
        tbar = _NavBar(self,self.canvas,frm)
        
        self.ax.legend(loc=2,borderaxespad=0.2,numpoints=1)
        
        # show the canvas and pack it
        self.canvas.show()
        self.canvas.get_tk_widget().pack(side=TOP,fill=BOTH,expand=1)

    def _plotsoi(self,this,allsites,indexed,gc,current):
        """
         plot the soi this: sites, lobs and cuts returns a list of locations plotted
        """
        # get config crap
        lobDist = gc['lobDist']
        msize = gc['msize']
        cutcolors = gc['cutcolors']
        
        # soi sites and lobs
        i = 0
        locs = []
        for site in this.pri:
            # get next site, location convert to lat/lon and project
            # NOTE: we only plot if this site has not already been plotted
            s = this.sites[site]
            (lat,lon) = _MGRS.toLatLon(s.location)
            x,y = self.base(lon,lat)
            
            # we could overlabel if for example, there are three 
            # times but the site is in only 2 unique locations so check first 
            plotted = False
            for ptl in self.ptLabels:
                if ptl[0] == x and ptl[1] == y:
                    if ptl[2].split('[')[0] == s.name:
                        plotted = True
                        break
            
            # have we already added this site to the index?
            add2index = False
            if not site in indexed:
                indexed.append(site)
                add2index = True
                            
            if not plotted:
                # add a label if this is the first time the site is being plotted
                if add2index:
                    self.base.plot(x,y,allsites[s.name]['color']+'o',\
                                   markersize=msize,label=s.name)
                else:
                    self.base.plot(x,y,allsites[s.name]['color']+'o',\
                                   markersize=msize)
                self.base.plot(x,y,'w+',markersize=msize)
                if len(allsites[s.name]['locations']) == 1:
                    l = s.name
                else:
                    l = "%s$_%d$" % (s.name,allsites[s.name]['locations'].index(s.location)+1)
                self.ptLabels.append((x,y,l))
            
            # get end pt of site's lob
            (lat1,lon1,mgrs1,baz) = terminus(s.location,s.lob,lobDist)
            x1,y1 = self.base(lon1,lat1)
            self.base.plot([x,x1],[y,y1],allsites[s.name]['color'])
            self.ptLabels.append((x1,y1,"t$_%d$ %d%s" % ((current+1),s.lob,u'\N{DEGREE SIGN}')))
            
            # store site and terminus
            locs.extend([s.location,mgrs1])
            
            # increase sitecolor index
            i += 1
        
        # plot any fixes
        if this.df.state == soi.DF_FIX:
            # a fix, plot location of the first cut
            (lat,lon) = _MGRS.toLatLon(this.df.fix)
            x,y = self.base(lon,lat)
            # instead of labeling with MGRS location, label with callsign
            cs = self.cnv.cs[self.cnv.order[current]]
            if cs is None: cs = "UI"
            self.ptLabels.append((x,y,cs))
            self.base.plot(x,y,cutcolors[0]+'s',markersize=msize)
            self.base.plot(x,y,'w*',markersize=msize)
        elif this.df.state >= soi.DF_CUT:
            # multiple cuts, plot all
            i = 0
            for cut in this.df.cuts:
                # for each cut, get location, convert to lat,lon and project onto map
                (lat,lon) = _MGRS.toLatLon(cut[soi.DF_CUT_X])
                x,y = self.base(lon,lat)
                cs = self.cnv.cs[self.cnv.order[current]]
                if cs is None: cs = "UI"
                self.ptLabels.append((x,y,cs))
                self.base.plot(x,y,cutcolors[i]+'s',markersize=msize)
                self.base.plot(x,y,'w*',markersize=msize)
                
                # incr the cutcolor index
                i += 1
        
        """
        # is there a polygon to fill with the cuts?
        # TODO some polygons (soi 1) do not fill in the polygon completely
        if len(this.df.cuts) >= 3:
            lons = []
            lats = []
            for cut in this.df.cuts:
                (lat,lon) = _MGRS.toLatLon(cut[6]) 
                lats.append(lat)
                lons.append(lon)
            xs,ys = self.base(lons,lats)
            xy = np.vstack([xs,ys]).T   
            p = Polygon(xy,closed=True,facecolor='black',linewidth=1,alpha=0.4)        
            self.fig.gca().add_patch(p)
        """
        
        return locs

class ViewSOIPanel(ChildPanel):
    """
     Displays SOI details and allows for edit of Gist
    """
    def __init__(self,tl,parent,key,soi):
        self.key = key
        self.soi = soi
        ChildPanel.__init__(self,tl,parent,"SOI %d" % key,"img/icom.png")

    # CALLBACKS 

    def addcallsign(self):
        """ tags/untags selected text in Gist as a callsign by underlining it """
        try:
            tags = self.txtGist.tag_names("sel.first")
            if "cs" in tags:
                self.txtGist.tag_remove("cs","sel.first","sel.last")
            else:
                self.txtGist.tag_add("cs","sel.first","sel.last")
        except TclError:
            pass

    def save(self): 
        """ save the 'new' gist have to validate first """
        try:
            gist = self.txtGist.get('1.0',END)
            opnote = self.txtOpNote.get('1.0',END)
            dtg = dt.datetime.strptime(self.txtSOIDate.get()+" "+\
                                       self.txtSOITU.get(),"%Y-%m-%d %H%M")
            if self.parent.config.ui['dtime'] == 'local':
                dtg = l2z(dtg,self.parent.config.ui['z2l'])
            rf = float(self.txtSOIRF.get())
        except Exception, e:
            print e
            showerror("Invalid SOI","SOI parameters are invalid")
        else:
            # for tags, we just delete and readd
            self.soi.setdtg(dtg)
            self.soi.setrf(rf)
            self.soi.setgist(gist)
            self.soi.callsigns = []
            tags = self.txtGist.tag_ranges("cs")
            for k in xrange(0,len(tags)-1,2):
                self.soi.addcallsign(self.txtGist.get(tags[k],tags[k+1]),\
                                     str(tags[k]),str(tags[k+1]))
            self.soi.setopnote(opnote)
            self.parent.savesoi(self.key,self.soi)
            self.parent.childclose(self._name)

    def gistselect(self,event):
        """ bind left mouse button release, if selection, enable callsign button """
        # TODO is there a better way of responding to selection than using TclError
        try:
            self.txtGist.tag_names("sel.first")
            self.btnCallsign.config(state=NORMAL)
        except TclError:
            # no selection, disable add callsign button
            self.btnCallsign.config(state=DISABLED)

    # PRIVATE FCTS
    
    def _makegui(self):
        """ make the gui & initialize with soi """
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)
        
        frmSOI = Frame(frm)
        frmSOI.grid(row=0,column=0,sticky=W)
        frmLOBs = Frame(frm)
        frmLOBs.grid(row=1,column=0,sticky=W)
        frmDF = Frame(frm)
        frmDF.grid(row=2,column=0,sticky=W)
        frmBtn = Frame(frm)
        frmBtn.grid(row=3,column=0,sticky=N)
        
        # SOI DETAILS
        # time label and time conversion
        tLBL = "TU (Z)"
        dtg = self.soi.dtg
        if self.parent.config.ui['dtime'] == 'local':
            tLBL = "TU (L):"
            dtg = z2l(dtg,self.parent.config.ui['z2l'])

        # the widgets        
        Label(frmSOI,text="Date:").grid(row=0,column=0,sticky=W)
        self.txtSOIDate = Entry(frmSOI,width=10)
        self.txtSOIDate.grid(row=0,column=1,sticky=W)
        self.txtSOIDate.insert(0,dtg.strftime("%Y-%m-%d"))
        Label(frmSOI,text=tLBL).grid(row=0,column=2,sticky=W)
        self.txtSOITU = Entry(frmSOI,width=4)
        self.txtSOITU.grid(row=0,column=3,sticky=W)
        self.txtSOITU.insert(0,dtg.strftime("%H%M"))
        Label(frmSOI,text="RF:").grid(row=0,column=4,sticky=W)
        self.txtSOIRF = Entry(frmSOI,width=7)
        self.txtSOIRF.grid(row=0,column=5,sticky=W)
        self.txtSOIRF.insert(0,self.soi.rf)
        Label(frmSOI,text="Gist:").grid(row=1,column=0,sticky=W)
        self.txtSGist = ScrolledText(frmSOI)
        self.txtGist = self.txtSGist.text
        self.txtGist.config(width=40)
        self.txtGist.config(height=2)
        self.txtGist.config(wrap=WORD)
        self.txtSGist.grid(row=1,column=1,columnspan=5,rowspan=2,sticky=W)
        self.txtGist.tag_config("cs",underline=1) # callsign tag (underlined)
        if self.soi.gist: self.txtGist.insert("1.0",self.soi.gist)
        for cs in self.soi.getcallsigns(): self.txtGist.tag_add("cs",cs[1],cs[2])
        if self.parent._imgCallsign:
            self.btnCallsign = Button(frmSOI,image=self.parent._imgCallsign,command=self.addcallsign)
        else:
            self.btnCallsign = Button(frmSOI,text="CS",command=self.addcallsign)
        self.btnCallsign.grid(row=2,column=0,sticky=W)
        self.btnCallsign.config(state=DISABLED)
        Label(frmSOI,text="Note:").grid(row=3,column=0,sticky=W)
        self.txtSOpNote = ScrolledText(frmSOI)
        self.txtOpNote = self.txtSOpNote.text
        self.txtOpNote.config(width=40)
        self.txtOpNote.config(height=2)
        self.txtOpNote.config(wrap=WORD)
        self.txtSOpNote.grid(row=3,column=1,columnspan=5,rowspan=2,sticky=W)
        if self.soi.opnote: self.txtOpNote.insert("1.0",self.soi.opnote)
        
        # LOBs section
        # headers change timezone if necessary
        if self.parent.config.ui['azimuth'] == 'grid': nLBL = "LOB (GN)"
        elif self.parent.config.ui['azimuth'] == 'magnetic': nLBL = "LOB (MN)"
        else: nLBL = "LOB (TN)"
        Label(frmLOBs,text="Location",width=15).grid(row=0,column=1,sticky=E)
        Label(frmLOBs,text=nLBL,width=10).grid(row=0,column=2,sticky=E)
        for i in range(len(self.soi.pri)):
            Label(frmLOBs,text=self.soi.pri[i]).grid(row=i+1,column=0,sticky=W)
            Label(frmLOBs,text="%s" % self.soi.sites[self.soi.pri[i]].location).grid(row=i+1,column=1,sticky=E)
            lob = self.soi.sites[self.soi.pri[i]].lob
            if self.parent.config.ui['azimuth'] != 'true':
                lob = convertazimuth(self.parent.config.ui['azimuth'],'true',lob,self.parent.config.declination)
            Label(frmLOBs,text="%.1f" % lob).grid(row=i+1,column=2,sticky=E)
        
        # DF section
        # make a quad with site names on vertical and horizontal (by priority)
        # n = # of sites, we have a (n+1) x n+1) quad with vertical & horizontal
        # labels of sites in order of priority

        # the 0,0 cell, make it raised and the width of the longest site name
        w = 1
        for i in range(len(self.soi.pri)):
            if len(self.soi.pri[i]) > w: w = len(self.soi.pri[i])
        Label(frmDF,text="",width=w,relief='raised').grid(row=0,column=0,sticky=N+W)
        
        # horizontal,vertical labels
        for i in range(len(self.soi.pri)):
            Label(frmDF,text=self.soi.pri[i],width=15,relief='raised').grid(row=0,column=i+1,sticky=N)
            Label(frmDF,text=self.soi.pri[i],relief='raised').grid(row=i+1,column=0,sticky=W)
        
        # add cuts for inner tables 
        for r in range(len(self.soi.pri)):
            for c in range(len(self.soi.pri)):
                if r == c: Label(frmDF,text="----------",width=15,relief='sunken').grid(row=r+1,column=c+1,sticky=N)
                else:
                    cut = self.soi.df.getcut(self.soi.pri[r],self.soi.pri[c])
                    Label(frmDF,text=cut,width=15,relief='sunken').grid(row=r+1,column=c+1,sticky=N)
        
        # add the final deterimination
        Label(frmDF,text="Location: %s" % self.soi.df.status).grid(row=r+2,column=0,columnspan=len(self.soi.pri)+1,sticky=W)
        
        # fsave and close buttons
        Button(frmBtn,text="Save",command=self.save).grid(row=0,column=0,sticky=W)
        Button(frmBtn,text="Close",command=self.closeapp).grid(row=0,column=1,sticky=W)
        
        # callbacks
        self.txtGist.bind('<ButtonRelease-1>',self.gistselect)

class ViewConvoPanel(ChildPanel):
    """
     Displays Convo details and allows
    """
    def __init__(self,tl,parent,key,cnv):
        self.key = key
        self.cnv = cnv
        ChildPanel.__init__(self,tl,parent,"Convo %d" % key,"img/icom.png")

#### CALLBACKS

    def save(self):
        """ saves changes if any and closes """
        # has the order changed?
        order = []
        for txtOrder in self.txtOrder:
            try:
                # ensure order is valid & coherent, must be an integer, nothing
                # larger than # of sois, nothing less than 1 & no duplicates
                o = int(txtOrder.get())
                if o < 1 or o > len(self.cnv.keys):
                    showerror("Invalid","Order must between 1 and %d" % len(self.cnv.keys))
                    return
                if o in order:
                    print o
                    print order
                    showerror("Invalid","%d already exists in order" % o)
                    return
                order.append(o) 
            except:
                showerror("Invalid","Order must be numeric")
                return
        self.cnv.order = map(lambda o:o-1,order) # subtract 1 for zero-indexing of list
        self.cnv.sender = self.cnv.keys[self.cnv.order[0]]
        
        # callsigns changed ?
        cs = []
        for o in self.cnv.order:
            emit = self.vCS[self.cnv.keys[o]].get()
            if emit == 'None': emit = None
            cs.append(emit)
        self.cnv.cs = cs
        
        # notify and close
        self.parent.savesoi(self.key,self.cnv)
        self.parent.childclose(self._name)

#### PRIVATE FCTS

    def _makegui(self):
        """ make and intialize the gui """
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)
        
        # 2 major frames - one for making changes, 1 for viewing the convo
        frmView = Frame(frm)
        frmView.grid(row=0,column=0,sticky=W+N+E+S)
        frmEdit = Frame(frm)
        frmEdit.grid(row=1,column=0,sticky=W+N+E+S)
        
        # In view frame, show rf, dtg, gist, opnote
        Label(frmView,text="Convo Details").grid(row=0,column=0,sticky=W)
        frmSOI = Frame(frmView)
        frmSOI.grid(row=1,column=0,sticky=W)
        frmText = Frame(frmView)
        frmText.grid(row=2,column=0,sticky=W)
        
        # add soi detail widgets
        frmDTG = Frame(frmSOI)
        frmDTG.grid(row=0,column=0,sticky=W)
        Label(frmDTG,text="Date: ").grid(row=0,column=0,sticky=W)
        self.txtDate = Entry(frmDTG,width=10,disabledforeground="black",cursor="circle")
        self.txtDate.grid(row=0,column=1,sticky=W)
        frmJustify = Frame(frmSOI)
        frmJustify.grid(row=1,column=0,sticky=W)
        Label(frmJustify,text="SID").grid(row=0,column=1,sticky=W)
        Label(frmJustify,text="TU (%s)" % self.parent.config.ui['dtime'][0].upper()).grid(row=0,column=2,sticky=W)
        Label(frmJustify,text="RF").grid(row=0,column=3,sticky=W)
        Label(frmJustify,text="CS").grid(row=0,column=4,sticky=W)
        Label(frmJustify,text="Location").grid(row=0,column=5,sticky=W)
        Label(frmJustify,text="Sender:").grid(row=1,column=0,sticky=W)
        Label(frmJustify,text="Responses:").grid(row=2,column=0,sticky=W)
        
        # get the sender object & configure details
        snd = self.parent._sois[self.cnv.sender]
        dtg = snd.dtg
        if self.parent.config.ui['dtime'] == 'local': dtg = l2z(dtg,self.parent.config.ui['z2l'])
        cs = self.cnv.cs[self.cnv.order[0]]
        if cs is None: cs = 'UI'
        strDF = ""
        dfState = snd.df.state
        if dfState == soi.DF_NONE:
            strDF = "None"
        elif dfState == soi.DF_LOB:
            strDF = snd.df.status
        elif dfState == soi.DF_CUT:
            strDF = snd.df.status[-15:]
        elif dfState == soi.DF_AMB_CUT:
            strDF = "Amb Cuts"
        elif dfState == soi.DF_FIX:
            strDF = snd.df.fix
        else:
            # should never get here
            strDF = "Fucked"
        
        # create & init sender details
        self.txtDate.insert(0,dtg.date().strftime("%Y-%m-%d"))
        self.txtDate.config(state=DISABLED)
        self.txtSNDID = Entry(frmJustify,width=3,disabledforeground="black",cursor="circle")
        self.txtSNDID.grid(row=1,column=1,sticky=W)
        self.txtSNDID.insert(0,self.cnv.sender)
        self.txtSNDID.config(state=DISABLED)
        self.txtSNDTU = Entry(frmJustify,width=5,disabledforeground="black",cursor="circle")
        self.txtSNDTU.grid(row=1,column=2,sticky=W)
        self.txtSNDTU.insert(0,dtg.time().strftime("%H%M"))
        self.txtSNDTU.config(state=DISABLED)
        self.txtSNDRF = Entry(frmJustify,width=7,disabledforeground="black",cursor="circle")
        self.txtSNDRF.grid(row=1,column=3,sticky=W)
        self.txtSNDRF.insert(0,"%.3f" % snd.getrf())
        self.txtSNDRF.config(state=DISABLED)
        self.txtSNDCS = Entry(frmJustify,width=7,disabledforeground="black",cursor="circle")
        self.txtSNDCS.grid(row=1,column=4,sticky=W)
        self.txtSNDCS.insert(0,cs)
        self.txtSNDCS.config(state=DISABLED)
        self.txtSNDLoc = Entry(frmJustify,width=15,disabledforeground="black",cursor="circle")
        self.txtSNDLoc.grid(row=1,column=5,sticky=W)
        self.txtSNDLoc.insert(0,strDF)
        self.txtSNDLoc.config(state=DISABLED)
        
        # despite redundancy of looping over convo signals twice, its easier
        # to add the details of responses here
        r = 2
        for o in self.cnv.order[1:]: # skip the first
            # get the current responder object & configure details
            rsp = self.parent._sois[self.cnv.keys[o]]
            dtg = rsp.dtg
            if self.parent.config.ui['dtime'] == 'local': dtg = l2z(dtg,self.parent.config.ui['z2l'])
            cs = self.cnv.cs[o]
            if cs is None: cs = 'UI'
            strDF = ""
            dfState = rsp.df.state
            if dfState == soi.DF_NONE:
                strDF = "None"
            elif dfState == soi.DF_LOB:
                strDF = rsp.df.status
            elif dfState == soi.DF_CUT:
                strDF = rsp.df.status[-15:]
            elif dfState == soi.DF_AMB_CUT:
                strDF = "Amb Cuts"
            elif dfState == soi.DF_FIX:
                strDF = rsp.df.fix
            else:
                # should never get here
                strDF = "Fucked"
        
            # create & init sender details
            txtRSPID = Entry(frmJustify,width=3,disabledforeground="black",cursor="circle")
            txtRSPID.grid(row=r,column=1,sticky=W)
            txtRSPID.insert(0,self.cnv.keys[o])
            txtRSPID.config(state=DISABLED)
            txtRSPTU = Entry(frmJustify,width=5,disabledforeground="black",cursor="circle")
            txtRSPTU.grid(row=r,column=2,sticky=W)
            txtRSPTU.insert(0,dtg.time().strftime("%H%M"))
            txtRSPTU.config(state=DISABLED)
            txtRSPRF = Entry(frmJustify,width=7,disabledforeground="black",cursor="circle")
            txtRSPRF.grid(row=r,column=3,sticky=W)
            txtRSPRF.insert(0,"%.3f" % snd.getrf())
            txtRSPRF.config(state=DISABLED)
            txtRSPCS = Entry(frmJustify,width=7,disabledforeground="black",cursor="circle")
            txtRSPCS.grid(row=r,column=4,sticky=W)
            txtRSPCS.insert(0,cs)
            txtRSPCS.config(state=DISABLED)
            txtRSPLoc = Entry(frmJustify,width=15,disabledforeground="black",cursor="circle")
            txtRSPLoc.grid(row=r,column=5,sticky=W)
            txtRSPLoc.insert(0,strDF)
            txtRSPLoc.config(state=DISABLED)
            
            r += 1
        
        # add two text fields for gist and opnote - these will be inserted later
        Label(frmText,text="GISTs").grid(row=0,column=0)
        self.txtSGist = ScrolledText(frmText)
        self.txtGist = self.txtSGist.text
        self.txtGist.config(width=40)
        self.txtGist.config(height=2)
        self.txtGist.config(wrap=WORD)
        self.txtGist.config(cursor="circle")
        self.txtSGist.grid(row=0,column=1,sticky=W) 
        Label(frmText,text="Op Notes").grid(row=1,column=0)
        self.txtSOpNote = ScrolledText(frmText)
        self.txtOpNote = self.txtSOpNote.text
        self.txtOpNote.config(width=40)
        self.txtOpNote.config(height=2)
        self.txtOpNote.config(wrap=WORD)
        self.txtOpNote.config(cursor="circle")
        self.txtSOpNote.grid(row=1,column=1,sticky=W)
        
        # In edit frame, two frames, one for editing order, callsigns, one
        # for buttons
        Label(frmEdit,text="Edit Convo").grid(row=0,column=0,sticky=W)
        frmSel = Frame(frmEdit)
        frmSel.grid(row=1,column=0,sticky=W+N+E+S)
        frmBtn = Frame(frmEdit)
        frmBtn.grid(row=2,column=0,sticky=N)
                
        # subframes
        frmOrder = Frame(frmSel)
        frmOrder.grid(row=0,column=0,sticky=W+N)
        frmCS = Frame(frmSel)
        frmCS.grid(row=0,column=1,sticky=E+N)
        
        # header labels above corresponding frames
        Label(frmOrder,text="Order").grid(row=0,column=0,columnspan=2,sticky=W)
        Label(frmCS,text="Callsigns").grid(row=0,column=0,columnspan=2,sticky=W)
        
        # add edit part, also concat gists and op notes
        self.txtOrder = []
        self.vCS = {}
        gist = ""
        opnote = ""
        for i in xrange(len(self.cnv.order)):
            o = self.cnv.order[i] # index of key,cs
            
            # soi order - use a text box with # to designate the order of the sois
            txtOrder = Entry(frmOrder,width=1)
            txtOrder.grid(row=i+1,column=0,sticky=W)
            txtOrder.insert(0,"%d" % (i+1))
            self.txtOrder.append(txtOrder)
            Label(frmOrder,text="SOI %d" % self.cnv.keys[o]).grid(row=i+1,column=1,sticky=E)
            
            # associated callsigns
            Label(frmCS,text="SOI %d" % self.cnv.keys[o]).grid(row=i+1,column=0,sticky=E)
            callsigns = ['None']+self.parent._sois[self.cnv.keys[o]].getuniquecallsigns()
            self.vCS[self.cnv.keys[o]] = StringVar(self)
            self.vCS[self.cnv.keys[o]].set(self.cnv.cs[o])
            opt = Tkinter.OptionMenu(frmCS,self.vCS[self.cnv.keys[o]],*callsigns)
            opt.grid(row=i+1,column=1,sticky=W)
            
            # gist and opnote
            cs = self.cnv.cs[o]
            if cs is None: cs = "UI"
            gist += "%s: %s\n" % (cs,self.parent._sois[self.cnv.keys[o]].gist.strip())
            opnote += "%d %s\n" % (self.cnv.keys[o],self.parent._sois[self.cnv.keys[o]].opnote.strip())
        
        # fsave and close buttons
        Button(frmBtn,text="Save",command=self.save).grid(row=0,column=0,sticky=W)
        Button(frmBtn,text="Close",command=self.closeapp).grid(row=0,column=1,sticky=W)
        
        # fill in details
        print "--------",gist,"----------"
        self.txtGist.insert("1.0",gist)
        self.txtGist.config(state=DISABLED)
        self.txtOpNote.insert("1.0",opnote)
        self.txtOpNote.config(state=DISABLED)

class ConvoPanel(ChildPanel):
    """
     ConvoPanel - provides setup for merging sois into a conversation
    """
    def __init__(self,tl,parent,keys):
        # get the associated date from keys and order by tu
        self.keys = keys
        ChildPanel.__init__(self,tl,parent,"Create Convo","img/convo.png")

#### CALLBACKS 

    def merge(self):
        """ merge sois into a convo """
        # remove and prepend sender index to order
        sender = self.vSender.get()
        pri = self.keys.index(sender)
        self.order.remove(pri)
        self.order = [pri]+self.order
        
        # get associated callsigns for each soi
        cs = []
        for key in self.keys:
            emit = self.vCS[key].get()
            if emit == 'None': emit = None
            cs.append(emit)
        
        # call parent and close
        self.parent.mergesois(sender,self.order,self.keys,cs)
        self.parent.childclose(self._name)
        
#### PRIVATE FUNCTIONS

    def _makegui(self):
        """ make the gui & initialize with soi """
        # if any of the keys is a convo, 'flatten' the convo
        newkeys = []
        for key in self.keys:
            if type(self.parent._sois[key]) == type(Convo(None,None,None,None)):
                for skey in self.parent._sois[key].keys:
                    if skey not in newkeys:
                        newkeys.append(skey)
            else:
                newkeys.append(key)
        self.keys = newkeys

        # get the associated soi data from parent and sort the keys by tu
        self.sois = {}
        os = []
        for key in self.keys:
            # save the associated data, add tuple (key,dtg)
            self.sois[key] = self.parent._sois[key]
            os.append((key,self.sois[key].dtg))
        os.sort(key=lambda o:o[1])            # sort tuple (key,dtg) by dtg  
        
        self.order = []
        for o in os: self.order.append(self.keys.index(o[0]))
        
        # set up frames
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)
        
        # two frames, one for selecting sender and callsigns, one for buttons
        frmSel = Frame(frm)
        frmSel.grid(row=0,column=0,sticky=N)
        frmBtn = Frame(frm)
        frmBtn.grid(row=1,column=0,sticky=N)
        
        # selection sender frame
        frmSender = Frame(frmSel)
        frmSender.grid(row=0,column=0,sticky=W+N)
        
        Label(frmSender,text="Sender").grid(row=0,column=0)
        
        # we use an int variable initially set to earliest sender
        self.vSender = IntVar()
        self.vSender.set(self.keys[self.order[0]])
        
        i=1
        for key in self.keys:
            rb = Radiobutton(frmSender,text="soi %d" % key,value=key,variable=self.vSender)
            rb.grid(row=i,column=0,sticky=W)
            i+=1
        
        # associate callsigns frame
        frmCallsigns = Frame(frmSel)
        frmCallsigns.grid(row=0,column=1,sticky=E)
        
        # get callsigns for each data
        self.cs = {}
        self.vCS = {}
        for key in self.keys:
            self.cs[key] = ['None']+self.sois[key].getuniquecallsigns()
        
        Label(frmCallsigns,text="Callsigns").grid(row=0,column=0,columnspan=2)
        
        i=1
        for key in self.keys:
            Label(frmCallsigns,text="soi %d" % key).grid(row=i,column=0)
            self.vCS[key] = StringVar(self)
            self.vCS[key].set('None')
            optSites = Tkinter.OptionMenu(frmCallsigns,self.vCS[key],*self.cs[key])
            optSites.grid(row=i,column=1,sticky=W)
            i+=1
        
        # Buttons
        Button(frmBtn,text="Merge",command=self.merge).grid(row=0,column=0,sticky=W)
        Button(frmBtn,text="Close",command=self.closeapp).grid(row=0,column=1,sticky=E) 

class Convo(object):
    """
     placeholder for conversations
    """
    def __init__(self,sender,order,keys,cs):
        """
         sender - key of sending soi
         order - list of ordering, index into keys,cs
         keys - list of keys of sois in convo
         cs - list of callsigns associated with each soi
        """
        self.sender = sender
        self.order = order
        self.keys = keys
        self.cs = cs
        
class LobsterRTPanel(Frame):
    """
     LobsterRTPanel - entry panel. Defines a simple menu and fields for entering
     sites and SOIs.
    """
    def __init__(self,parent,fpath=None):
        # initialize basic Frame and setup
        Frame.__init__(self,parent)
        self.appicon = ImageTk.PhotoImage(Image.open("img/lobster.png"))
        self.master.protocol("WM_DELETE_WINDOW",self.closeapp)
        self.tk.call('wm','iconphoto',self.master._w,self.appicon)
        self.grid(sticky=W+N+E+S)
        parent.resizable(0,0)
        
        # variables
        self.config = None        # configuration
        self._imgLocked = None    # images for site lock,
        self._imgUnLocked = None  # site unlock
        self._imgRemove = None    # & site remove
        self._imgCallsign = None  # add callsign
        self._imgEnter = None     # enter soi
        self._imgTime = None      # update soi time
        self._imgG6SOI = None     # img for soi in g6 list
        self._imgG6Convo = None   # img for convo in g6 list
        self._dialogs = {}        # dict of open child dialogs
        self._txtSites = []       # list of site entry widgets
        self._sois = {}           # internal data bin
        self._nSOI = None         # internal record counter
        self._curFile = None      # the current file, data is saved to
        self._hasChanged = False  # has data changed
                
        # make the menu, read the config, make the gui and initialize
        self._readconf()
        self._makemenu()
        self._makegui()
        self._initialize()
        
        # passed a file?
        if fpath: self.openfile(fpath)

## MENU CALLBACKS

    def newfile(self):
        """ closes current and initializes new """
        if self._hasChanged:
            ans = askyesnocancel('Save First?','There is unsaved data, Save before opening new?')
            if ans is None: return
            elif ans:
                self.savefile()    
        self._closedialogs()
        self._closefile()
        self._initialize()
        self._filestatus(False)

    def openfile(self,fpath=None):
        """ opens a pickled g6 file """
        # if a file was not passed, open the file dialog
        if not fpath:
            fpath = askopenfilename(title='Open Green 6',\
                                    filetypes=[('Green 6 Files','*.g6')],\
                                    parent = self)
        if fpath:
            self._closedialogs()
            try:
                # load all data from file and close before adding to gui, etc
                fin = open(fpath,'rb')
                sites = pickle.load(fin)
                soiRec = pickle.load(fin)
                sois = pickle.load(fin)
                fin.close()
            except Exception, e:
                showerror('Failed to Open Green 6',e)
            else:
                # update gui
                self._closefile()
                
                # date and time (use now) converting if necessary
                n = dt.datetime.utcnow()
                if self.config.ui['dtime'] == 'local': n = z2l(n,self.config.ui['z2l'])
                self.txtSOIDate.insert(0,n.date().strftime("%Y-%m-%d"))
                self.txtSOITU.insert(0,n.time().strftime("%H%M"))
                
                # sites
                for i in range(len(sites)):
                    # convert time to local if necessary
                    dtg = dt.datetime.strptime(self.txtSOIDate.get()+" "+sites[i][0],"%Y-%m-%d %H%M")
                    if self.config.ui['dtime'] == 'local': dtg = z2l(dtg,self.config.ui['z2l']) 
                    self._txtSites[i][SITE_TU].insert(0,dtg.time().strftime("%H%M"))
                    self._txtSites[i][SITE_NAME].insert(0,sites[i][1])
                    self._txtSites[i][SITE_LOC].insert(0,sites[i][2])
                    self._txtSites[i][SITE_LOCKED] = sites[i][3]
                    
                    if sites[i][3]:
                        if self._imgLocked:
                            self._txtSites[i][SITE_BTN].config(image=self._imgLocked)
                        else:
                            self._txtSites[i][SITE_BTN].config(text="L")
                        self._txtSites[i][SITE_TU].config(state=DISABLED)
                        self._txtSites[i][SITE_NAME].config(state=DISABLED)
                        self._txtSites[i][SITE_LOC].config(state=DISABLED)
                    else:
                        if self._imgLocked:
                            self._txtSites[i][SITE_BTN].config(image=self._imgUnLocked)
                        else:
                            self._txtSites[i][SITE_BTN].config(text="U")
                        self._txtSites[i][SITE_TU].config(state=NORMAL)
                        self._txtSites[i][SITE_NAME].config(state=NORMAL)
                        self._txtSites[i][SITE_LOC].config(state=NORMAL)
                
                # sois
                self._nSOI = soiRec
                self._sois = sois
                
                # sort sois by tu and add in sorted order
                skeys = self._sois.keys()
                skeys.sort(key=lambda key:self._dtg(key))   
                for key in skeys: self._addgreen6(key,self._sois[key])
                
                # set the cur file and change the title
                self._curFile = fpath
                self._filestatus(False)

    def _dtg(self,key):
        """ returns the dtg of the soi corresponding to key """
        try:
            # attempt for an soi
            return self._sois[key].getdtg()
        except AttributeError:
            # its a convo, return sender
            return self._sois[self._sois[key].sender].getdtg()
       
    def savefile(self):
        """ saves the current pickled g6 file """
        # is there a file already in use
        if self._curFile:
            result = self._save(self._curFile)
            if not result: showinfo('Failed to Save',result)
            else: self._filestatus(False)
        else:
            fpath = asksaveasfilename(title='Save Green 6',\
                                      filetypes=[('Green 6 Files','*.g6')])
            if fpath:
                result = self._save(fpath)
                if result:
                    self._curFile = fpath
                    self._filestatus(False)
                else:
                    showinfo('Failed to Save',result)
    
    def saveasfile(self):
        """ saves the current pickled g6 file under a new name"""
        fpath = asksaveasfilename(title='Save Green 6 as...',\
                                  filetypes=[('Green 6 Files','*.g6')])
        if fpath:
            result = self._save(fpath)
            if result:
                self._curFile = fpath
                self._filestatus(False)
            else:
                showerror('Failed to Save',result)
    
    def exportfile(self):
        """ exports the current g6 file as a csv """
        # allow only 1 export file to be open
        # TODO: this should be modal
        dialog = self._getdialogs("exportcsv")
        if not dialog:
            # if there are no sois, don't export
            if not self._sois: showinfo("SOIS empty","There is nothing to export")
            else:
                sites = []
                for i in range(NUM_SITES): sites.append(self._txtSites[i][SITE_NAME].get())
                t = Toplevel()
                pnl = ExportCSVPanel(t,self,self._sois,sites)
                self._adddialog(pnl._name,Minion(t,pnl,"exportcsv",True))
        else:
            dialog[0].tk.deiconify()
            dialog[0].tk.lift()

    def configapp(self):
        """ open preferences panel """
        # allow only 1 preference panel to be open
        dialog = self._getdialogs("preferences")
        if not dialog:
            t = Toplevel()
            pnl = PreferencesPanel(t,self,self.config)
            self._adddialog(pnl._name,Minion(t,pnl,"preferences",True))
        else:
            dialog[0].tk.deiconify()
            dialog[0].tk.lift()

    def closeapp(self):
        # if there is unsaved date prompt to save data, otherwise, prompt to quit
        if self._hasChanged:
            ans = askyesnocancel('Save First?','There is unsaved data. Save before quitting')
            if ans is None: return
            elif ans:
                self.savefile()
            self._closedialogs(True)
            self.quit()
        else:
            ans = askquestion('Quit?','Really Quit?',parent=self)
            if ans == 'no':
                return
            else:
                # quit will handle closing dialogs but do it anyway
                self._closedialogs(True)
                self.quit()

    def convert(self):
        """ open conversion dialog """
        dialog = self._getdialogs("convert")
        if not dialog:
            t = Toplevel()
            pnl = ConversionPanel(t,self)
            self._adddialog(pnl._name,Minion(t,pnl,"convert",False))
        else:
            dialog[0].tk.deiconify()
            dialog[0].tk.lift()
    
    def distance(self):
        """ show distance/direction dialog """
        dialog = self._getdialogs("dd")
        if not dialog:
            t = Toplevel()
            pnl = DDPanel(t,self)
            self._adddialog(pnl._name,Minion(t,pnl,"dd",False))
        else:
            dialog[0].tk.deiconify()
            dialog[0].tk.lift()

    def cut(self):
        """ show cut dialog """
        dialog = self._getdialogs("cut")
        if not dialog:
            t = Toplevel()
            pnl = CutPanel(t,self)
            self._adddialog(pnl._name,Minion(t,pnl,"cut",False))
        else:
            dialog[0].tk.deiconify()
            dialog[0].tk.lift()

    def quadrant(self):
        """ show quadrant dialog """
        dialog = self._getdialogs("quadrant")
        if not dialog:
            t = Toplevel()
            pnl = QuadrantPanel(t,self)
            self._adddialog(pnl._name,Minion(t,pnl,"quadrant",False))
        else:
            dialog[0].tk.deiconify()
            dialog[0].tk.lift()

    def help(self):
        """ show the help dialog """
        # allow only 1
        dialog = self._getdialogs("help",False)
        if not dialog:
            t = Toplevel()
            pnl = HelpPanel(t,self)
            self._adddialog(pnl._name,Minion(t,pnl,"help",False))
        else:
            dialog[0].tk.deiconify()
            dialog[0].tk.lift()

    def about(self):
        """ show the about dialog """
        # allow only 1
        dialog = self._getdialogs("about",False)
        if not dialog:
            t = Toplevel()
            pnl = AboutPanel(t,self)
            self._adddialog(pnl._name,Minion(t,pnl,"about",False))
        else:
            dialog[0].tk.deiconify()
            dialog[0].tk.lift()        

## WIDGET CALLBACKS

    def settime(self):
        """ sets time up to current time """
        dtg = dt.datetime.utcnow()
        if self.config.ui['dtime'] == "local": dtg = z2l(dtg,self.config.ui['z2l'])
        self.txtSOIDate.delete(0,END)
        self.txtSOIDate.insert(0,dtg.date().strftime("%Y-%m-%d"))
        self.txtSOITU.delete(0,END)
        self.txtSOITU.insert(0,dtg.time().strftime("%H%M"))

    def soienter(self):
        """
         adds soi and site information into internal data and into list
        """
        s = self._validate()
        if s:
            # is there a cut?
            s.triangulate(self.config.geo['cutt'])
            
            # add to internal and to display list
            self._sois[self._nSOI]=s
            self._addgreen6(self._nSOI,s)
            self._nSOI += 1

            # clear LOBs/RF for next entry and set focus to first site
            for i in range(NUM_SITES): self._txtSites[i][SITE_LOB].delete(0,END)
            self.txtSOIRF.delete(0,END)
            self.txtGist.delete("1.0",END)
            self.txtOpNote.delete("1.0",END)
            self._txtSites[0][SITE_LOB].focus_set()
            self.btnCallsign.config(state=DISABLED)
            self._filestatus(True)
 
    def sitelock(self,i):
        """ lock the row, except lob, at i """
        row = i-1
        if self._txtSites[row][SITE_LOCKED]:
            # unlock, allow edits for all
            self._txtSites[row][SITE_LOCKED] = False
            if self._imgLocked:
                self._txtSites[row][SITE_BTN].config(image=self._imgUnLocked)
            else:
                self._txtSites[row][SITE_BTN].config(text="U")
            self._txtSites[row][SITE_TU].config(state=NORMAL)
            self._txtSites[row][SITE_NAME].config(state=NORMAL)
            self._txtSites[row][SITE_LOC].config(state=NORMAL)
        else:
            # lock, only allow edits for LOB field
            self._txtSites[row][SITE_LOCKED] = True
            if self._imgLocked:
                self._txtSites[row][SITE_BTN].config(image=self._imgLocked)
            else:
                self._txtSites[row][SITE_BTN].config(text="U")
            self._txtSites[row][SITE_TU].config(state=DISABLED)
            self._txtSites[row][SITE_NAME].config(state=DISABLED)
            self._txtSites[row][SITE_LOC].config(state=DISABLED)

    def siteremove(self,i):
        """ remove the entries in row """
        # TODO why is it necessary to do twice
        self._clearsiterow(i-1)
        self._clearsiterow(i-1)

    def addcallsign(self):
        """ tags/untags selected text in Gist as a callsign by underlining it """
        # should never get here unless something is selected
        tags = self.txtGist.tag_names("sel.first")
        if "cs" in tags:
            self.txtGist.tag_remove("cs","sel.first","sel.last")
        else:
            self.txtGist.tag_add("cs","sel.first","sel.last")

## LIST BINDINGS
    
    def rcmenu(self,event):
        """ show context menu on right click """
        # make context menu
        mnu = Menu(None,tearoff=0)
        mnu.add_command(label="Unselect",command=lambda:self.ukp(None))
        mnu.add_command(label="Delete",command=lambda:self.dkp(None))
        mnu.add_separator()
        mnu.add_command(label="View/Edit",command=lambda:self.vkp(None))
        mnu.add_command(label="Map",command=lambda:self.mkp(None))
        mnu.add_separator()
        mnu.add_command(label="Convo",command=lambda:self.ckp(None))

        # cannot map or edit multiple signals, have to select and open each one
        n = len(self.g6.info_selection())
        if n == 0: return
        elif n == 1: mnu.entryconfig(6,state=DISABLED) # disable convo
        elif n > 1:
            mnu.entryconfig(3,state=DISABLED) # disable edit
            mnu.entryconfig(4,state=DISABLED) # disable map
        mnu.tk_popup(event.x_root,event.y_root,"")
    
    def ukp(self,event):
        """ unselect current selected """
        self.g6.selection_clear()
    
    def dkp(self,event):
        """ delete current selected entry from list and internal data """
        ss = self.g6.info_selection()
        for s in ss:
            # delete from internal and remove from g6 list
            del self._sois[int(s)]
            self.g6.delete_entry(s)
            
            # delete from any convos
            rConvo = []
            for soi in self._sois:
                if type(self._sois[soi]) == type(Convo(None,None,None,None)):
                    # attempt to remove this key from convos set of keys
                    try:
                        # we have to delete from key,order and callsign
                        i = self._sois[soi].keys.index(int(s))
                        self._sois[soi].keys.pop(i)
                        self._sois[soi].keys.pop(i)
                        self._sois[soi].cs.pop(i)
                        
                        # was this the sender ?, make it next in order
                        if self._sois[soi].sender == int(s):
                            self.sender = self._sois[soi].keys[self.order[0]]
                        
                        # identify convos with 1 or fewer sois
                        if len(self._sois[soi].keys) <= 1:
                            rConvo.append(soi)
                    except ValueError:
                        pass
            
            # delete any convos with empty keys
            if rConvo:
                showinfo("Removing Convos","Convos %s are now invalid, removing them" % ", ".join(map(str,rConvo)))
                for r in rConvo:
                    del self._sois[r]
                    self.g6.delete_entry(r)
        self._filestatus(True)

    def vkp(self,event):
        """ display the selected record """
        # allow multiple panels but only 1 per key
        sid = int(self.g6.info_selection()[0])
        if type(self._sois[sid]) == type(Convo(None,None,None,None)):
            # open a convo dialog
            dialog = self._getdialogs("convo_%d" % sid,False)
            if not dialog:
                t = Toplevel()
                pnl = ViewConvoPanel(t,self,sid,self._sois[sid])
                self._adddialog(pnl._name,Minion(t,pnl,"convo_%d" % sid,True))
            else:
                dialog[0].tk.deiconify()
                dialog[0].tk.lift()
        else:
            # open a soi dialog
            dialog = self._getdialogs("soi_%d" % sid,False)
            if not dialog:
                t = Toplevel()
                pnl = ViewSOIPanel(t,self,sid,self._sois[sid])
                self._adddialog(pnl._name,Minion(t,pnl,"soi_%d" % sid,True))
            else:
                dialog[0].tk.deiconify()
                dialog[0].tk.lift()
            
    def mkp(self,event):
        """ display selected on map """
        # allow multiple MapPanels but only 1 per key
        sid = int(self.g6.info_selection()[0])
        if type(self._sois[sid]) == type(Convo(None,None,None,None)):
            dialog = self._getdialogs("convomap_%d" % sid,False)
            if not dialog:
                t = Toplevel()
                pnl = ConvoMapPanel(t,self,sid,self._sois[sid])
                self._adddialog(pnl._name,Minion(t,pnl,"convomap_%d" % sid,True))
            else:
                dialog[0].tk.deiconify()
                dialog[0].tk.lift()
        else:
            dialog = self._getdialogs("map_%d" % sid,False)
            if not dialog:
                t = Toplevel()
                pnl = MapPanel(t,self,sid,self._sois[sid])
                self._adddialog(pnl._name,Minion(t,pnl,"map_%d" % sid,True))
            else:
                dialog[0].tk.deiconify()
                dialog[0].tk.lift()

    def ckp(self,event):
        """ merge 2 or more sois into a conversation """
        ss = self.g6.info_selection()
        dialog = self._getdialogs("convo",False)
        if not dialog:
            ss = map(int,ss)
            t = Toplevel()
            pnl = ConvoPanel(t,self,ss)
            self._adddialog(pnl._name,Minion(t,pnl,"convo",True))
        else:
            dialog[0].tk.deiconify()
            dialog[0].tk.lift()
     
## ENTRY BINDINGS 
    
    def krlob(self,event):
        """ lob entry key release, if up or down arrows, move to next lob """
        # we're only concerned with up or down arrow keys
        if event.keysym == 'Up': etype = 'up'
        elif event.keysym == 'Down': etype = 'down'
        else:
            return
        
        # what site lob is this?
        nSite = -1
        for i in range(NUM_SITES):
            if event.widget._name == self._txtSites[i][SITE_LOB]._name:
                nSite = i
                break
        
        # something went terribly wrong if this fails
        if nSite < 0 or nSite >= NUM_SITES: return
        
        # up will always go to previous site lob (unless this is first site)
        if etype == "up":
            if nSite == 0: return
            self._txtSites[nSite-1][SITE_LOB].focus_set()
        else:
            # down is different, if this is the last site or the next site
            # has no entry, jump to RF
            if nSite == NUM_SITES -1: self.txtSOIRF.focus_set()
            else:
                if self._txtSites[nSite+1][SITE_NAME].get() == "":
                    self.txtSOIRF.focus_set()
                else:
                    self._txtSites[nSite+1][SITE_LOB].focus_set()

    def krrf(self,event):
        """ bind up/down arrow keys in RF entry """
        # down will cycle through to first LOB, up will go to last site
        if event.keysym == 'Down':
            self.txtGist.focus_set()
        elif event.keysym == "Up":
            # find the last site with entries
            nSite = 0
            for i in range(NUM_SITES-1,0,-1):
                if self._txtSites[i][SITE_NAME].get() != "":
                    nSite = i
                    break
            self._txtSites[nSite][SITE_LOB].focus_set()

    def br1gist(self,event):
        """ bind left mouse button release, if selection, enable callsign button """
        try:
            self.txtGist.tag_names("sel.first")
            self.btnCallsign.config(state=NORMAL)
        except TclError:
            # no selection, disable add callsign button
            self.btnCallsign.config(state=DISABLED)
  
    def krgist(self,event):
        """ bind up/down arrow keys """
        # down will give focus to op note, up will give focus to rf
        if event.keysym == 'Down':
            self.txtOpNote.focus_set()
        elif event.keysym == "Up":
            self.txtSOIRF.focus_set()

    def tabgist(self,event):
        """ don't insert tabs in gist, use to focus on next widget """
        self.txtOpNote.focus_set()
        return "break"
        
    def kropnote(self,event):
        """ bind up/down arrow keys """
        if event.keysym == 'Down':
            self.btnEnter.focus_set()
        elif event.keysym == "Up":
            self.txtGist.focus_set()

    def tabopnote(self,event):
        """ don't insert tabs in op note, use to focus on next widget """
        self.btnEnter.focus_set()
        return "break"

    def krenter(self,event):
        """ bind Enter/Return press to set off btnEnter command """
        if event.keysym == "Return": self.soienter()

## CHILD WINDOW CALLBACKS 

    def childclose(self,pname):
        """ child window notifying of closing """
        self._deletedialog(pname)

    def savesoi(self,key,soi):
        """ saves the updated gist in soi to key """
        # save internally
        self._sois[key] = soi
        
        # update g6 list - for convos, no changes are reflected in list
        if type(soi) != type(Convo(None,None,None,None)):
            dtg = soi.getdtg()
            if self.config.ui['dtime'] == 'local': dtg = z2l(dtg,self.config.ui['z2l'])
            self.g6.item_configure(key,2,text=dtg.time().strftime("%H%M"))
            self.g6.item_configure(key,3,text=soi.rf)
        self._filestatus(True)
        
        # does edited soi affect any convos? only care about removed callsigns
        # TODO: add an info message saying some convos have been affected
        affected = []
        for soi in self._sois:
            if type(self._sois[soi]) == type(Convo(None,None,None,None)):
                # soi is a convo
                try:
                    # the edited soi is at index i in convo, append to affected
                    i=self._sois[soi].keys.index(key)
                    affected.append(self._sois[soi].keys[i])
                    
                    # if the callsign at i no longer exists in the soi, change it to None
                    if not self._sois[soi].cs[i] in self._sois[key].getuniquecallsigns():
                        self._sois[soi].css[i] = None
                    
                except ValueError:
                    # soi is not in convo
                    pass

        # showinfo message if any affected convos
        if affected:
            showinfo('Convos Affected','The edited SOI is part of convos %s' % ",".join(map(str,affected)))

    def mergesois(self,sender,order,keys,callsigns):
        """ merges selected sois into a convo """
        c = Convo(sender,order,keys,callsigns)
        self._sois[self._nSOI] = c
        self._addgreen6(self._nSOI,c)
        self._nSOI += 1
        self._filestatus(True)

    def changeprefs(self):
        """ preferences have changed, reload window """
        # if there is unsaved data, ask to save before reloading
        self._closedialogs(True) # we're reloading, so close everything
        if self._hasChanged:
           ans = askquestion('Save First?','Restarting program for changes to take effect. Save first?')
           if ans == 'yes': self.savefile()
        fpath = None
        if self._curFile: fpath=self._curFile
        restart(fpath)

## PRIVATE FUNCTIONS
        
    def _makemenu(self):
        self.menubar = Menu(self)
        
        # File Menu
        self.mnuFile = Menu(self.menubar,tearoff=0)
        self.mnuFile.add_command(label="New",command=self.newfile)
        self.mnuFile.add_command(label="Open...",command=self.openfile)
        self.mnuFile.add_separator()
        self.mnuFile.add_command(label="Save",command=self.savefile)
        self.mnuFile.add_command(label="Save As...",command=self.saveasfile)
        self.mnuFile.add_command(label="Export...",command=self.exportfile)
        self.mnuFile.add_separator()
        self.mnuFile.add_command(label="Quit",command=self.closeapp)
        
        # edit menu
        self.mnuEdit = Menu(self.menubar,tearoff=0)
        self.mnuEdit.add_command(label="Preferences",command=self.configapp)
        
        # utilities menu
        self.mnuUtils = Menu(self.menubar,tearoff=0)
        self.mnuUtils.add_command(label="Convert",command=self.convert)
        self.mnuUtils.add_separator()
        self.mnuUtils.add_command(label="Distance",command=self.distance)
        self.mnuUtils.add_separator()
        self.mnuUtilsTriang = Menu(self.mnuUtils,tearoff=0)
        self.mnuUtilsTriang.add_command(label="Cut",command=self.cut)
        self.mnuUtilsTriang.add_command(label="Quadrant",command=self.quadrant)
        self.mnuUtils.add_cascade(label="Triangulation",menu=self.mnuUtilsTriang)
        
        # help menu
        self.mnuHelp = Menu(self.menubar,tearoff=0)
        self.mnuHelp.add_command(label="Help",command=self.help)
        self.mnuHelp.add_separator()
        self.mnuHelp.add_command(label="About",command=self.about)
        
        # add to main
        self.menubar.add_cascade(label="File",menu=self.mnuFile)
        self.menubar.add_cascade(label="Edit",menu=self.mnuEdit)
        self.menubar.add_cascade(label="Utilities",menu=self.mnuUtils)
        self.menubar.add_cascade(label="Help",menu=self.mnuHelp)
        self.master.config(menu=self.menubar)

    def _makegui(self):
        # create, pack the frame
        frm = Frame(self)
        frm.pack(side=TOP,fill=BOTH,expand=TRUE)
        
        frmTop = Frame(frm)
        frmTop.grid(row=0,column=0,sticky=W)
        frmMid = Frame(frm)
        frmMid.grid(row=1,column=0,sticky=W)
        
        # SITE DETAILS
        # headers (change azimuth, timezone if necessary) 
        if self.config.ui['azimuth'] == 'grid': nLBL = "LOB (GN)"
        elif self.config.ui['azimuth'] == 'magnetic': nLBL = "LOB (MN)"
        else: nLBL = "LOB (TN)"
        if self.config.ui['dtime'] == 'local': tLBL = "TU (L)"
        else: tLBL = "TU (Z)"
        
        Label(frmTop,text="Site").grid(row=0,column=0,sticky=W)
        Label(frmTop,text=tLBL).grid(row=0,column=1,sticky=W)
        Label(frmTop,text="Name").grid(row=0,column=2,sticky=W)
        Label(frmTop,text="Location (MGRS)").grid(row=0,column=3,sticky=W)
        Label(frmTop,text=nLBL).grid(row=0,column=4,sticky=W)
        
        # Site(s)
        # load images for buttons
        try:
            self._imgLocked = ImageTk.PhotoImage(Image.open('img/locked.png'))
            self._imgUnLocked = ImageTk.PhotoImage(Image.open('img/unlocked.png'))
            self._imgRemove = ImageTk.PhotoImage(Image.open('img/remove.png'))
            self._imgCallsign = ImageTk.PhotoImage(Image.open('img/person.png'))
            self._imgEnter = ImageTk.PhotoImage(Image.open('img/add.png'))
            self._imgTime = ImageTk.PhotoImage(Image.open('img/time.png'))
            self._imgG6SOI = ImageTk.PhotoImage(Image.open('img/icom_16x16.png'))
            self._imgG6Convo = ImageTk.PhotoImage(Image.open('img/convo_16x16.png'))
        except:
            pass
            
        # NOTE: issues with looping over sites in terms of lambda call for
        # button command but calling in separate fct inside loop works
        self._txtSites = []
        for i in range(NUM_SITES): self._siterow(frmTop,i)

        # SOI
        # labels
        Label(frmMid,text="Date:").grid(row=0,column=0,sticky=W)
        Label(frmMid,text=tLBL+":").grid(row=0,column=2,sticky=W)
        Label(frmMid,text="RF:").grid(row=0,column=4,sticky=W)
        
        # for each entry assign validation command
        vdatecmd = self.register(self._validdate)
        self.txtSOIDate = Entry(frmMid,width=10,validate='key',\
                                validatecommand=(vdatecmd,'%d','%S','%P'))
        self.txtSOIDate.grid(row=0,column=1,sticky=W)
        
        vtimecmd = self.register(self._validtime)
        self.txtSOITU = Entry(frmMid,width=4,validate='key',\
                              validatecommand=(vtimecmd,'%d','%S','%P'))
        self.txtSOITU.grid(row=0,column=3,sticky=W)
        
        vrfcmd = self.register(self._validrf)
        self.txtSOIRF = Entry(frmMid,width=8,validate='key',\
                              validatecommand=(vrfcmd,'%d','%S','%P'))
        self.txtSOIRF.grid(row=0,column=5,sticky=W)
        
        if self._imgTime:
            self.btnSetTime = Button(frmMid,image=self._imgTime,command=self.settime)
        else:
            self.btnSetTime = Button(frmMid,text="T",command=self.settime)
        self.btnSetTime.grid(row=0,column=6,sticky=W)
        
        if self._imgEnter:
            self.btnEnter = Button(frmMid,image=self._imgEnter,command=self.soienter)
        else:
            self.btnEnter = Button(frmMid,text="Add",command=self.soienter)
        self.btnEnter.grid(row=0,column=7,sticky=E)
        
        Label(frmMid,text="GIST").grid(row=1,column=0,sticky=E)
        if self._imgCallsign:
            self.btnCallsign = Button(frmMid,image=self._imgCallsign,command=self.addcallsign)
        else:
            self.btnCallsign = Button(frmMid,text="CS",command=self.addcallsign)
        self.btnCallsign.grid(row=2,column=0,sticky=W)
        self.btnCallsign.config(state=DISABLED)    
        self.txtSGist = ScrolledText(frmMid)
        self.txtGist = self.txtSGist.text
        self.txtGist.config(width=43)
        self.txtGist.config(height=2)
        self.txtGist.config(wrap=WORD)
        self.txtSGist.grid(row=1,column=1,columnspan=7,rowspan=2,sticky=W)
        self.txtGist.tag_config("cs",underline=1) # callsign tag (underlined)
        Label(frmMid,text="Note").grid(row=3,column=0,sticky=W)
        self.txtSOpNote = ScrolledText(frmMid)
        self.txtOpNote = self.txtSOpNote.text
        self.txtOpNote.config(width=43)
        self.txtOpNote.config(height=2)
        self.txtOpNote.config(wrap=WORD)
        self.txtSOpNote.grid(row=3,column=1,columnspan=7,rowspan=2,sticky=W)
        
        # ENTERED SIGNALS
        self.slist = ScrolledHList(frmMid,options="hlist.columns 5 hlist.header 1")
        self.g6 = self.slist.hlist
        self.g6.config(selectforeground='white') 
        self.g6.config(separator='\t')
        self.g6.config(selectmode='extended')
        headers = ["ID","SITE(S)",tLBL,"RF","FIX/CUT"]
        style={}
        style['header'] = DisplayStyle(TEXT,refwindow=self.g6,anchor=CENTER)
        for i in range(len(headers)):
            self.g6.header_create(i,itemtype=TEXT,text=headers[i],style=style['header'])
        self.slist.grid(row=5,column=0,columnspan=8,sticky=NSEW)
        
        # BINDINGS
        
        # bind key release of RF for looping through, and focus on RF to change 
        # the TU for SOI
        self.txtSOIRF.bind('<KeyRelease>',self.krrf)
        
        # bind key release on Enter button
        self.btnEnter.bind('<KeyRelease>',self.krenter)
        
        # bind mouse button (left) release on gist to determine if there is a 
        # selection, bind key release on gist and op note for up/down arrow
        # and tab for focus
        self.txtGist.bind('<ButtonRelease-1>',self.br1gist)
        self.txtGist.bind('<KeyRelease>',self.krgist)
        self.txtGist.bind('<Tab>',self.tabgist)
        self.txtOpNote.bind('<KeyRelease>',self.kropnote)
        self.txtOpNote.bind('<Tab>',self.tabopnote)
        
        # set key short cut bindings for the list
        self.g6.bind('<Button-3>',self.rcmenu) # right click context menu
        self.g6.bind("u",self.ukp)             # unselect selected
        self.g6.bind("d",self.dkp)             # delete selected
        self.g6.bind("v",self.vkp)             # edit selected
        self.g6.bind("m",self.mkp)             # map selected
        self.g6.bind("c",self.ckp)             # create conversation

    def _clearsiterow(self,i):
        """ clears all entries in site row i """
        self._txtSites[i][SITE_TU].delete(0,END)
        self._txtSites[i][SITE_TU].config(state=NORMAL)
        self._txtSites[i][SITE_NAME].delete(0,END)
        self._txtSites[i][SITE_NAME].config(state=NORMAL)
        self._txtSites[i][SITE_LOC].delete(0,END)
        self._txtSites[i][SITE_LOC].config(state=NORMAL)
        self._txtSites[i][SITE_LOB].delete(0,END)
        self._txtSites[i][SITE_LOCKED] = False
        if self._imgLocked:
            self._txtSites[i][SITE_BTN].config(image=self._imgUnLocked)
        else:
            self._txtSites[i][SITE_BTN].config(text="U")

    def _siterow(self,frm,i):
        """ add row of site entry buttons at row i """
        Label(frm,text="%d:" % (i+1)).grid(row=i+1,column=0,sticky=E)
        
        vtimecmd = self.register(self._validtime)
        txtSiteTU = Entry(frm,width=5,validate='key',\
                          validatecommand=(vtimecmd,'%d','%S','%P'))
        txtSiteTU.grid(row=i+1,column=1,sticky=W)
        
        vnamecmd = self.register(self._validname)
        txtSiteName = Entry(frm,width=5,validate='key',\
                            validatecommand=(vnamecmd,'%d','%S','%P'))
        txtSiteName.grid(row=i+1,column=2,sticky=W)
        
        vloccmd = self.register(self._validlocation)
        txtSiteLoc = Entry(frm,width=15,validate='key',\
                           validatecommand=(vloccmd,'%d','%S','%P'))
        txtSiteLoc.grid(row=i+1,column=3,sticky=W)
        
        vlobcmd = self.register(self._validlob)
        txtSiteLOB = Entry(frm,width=8,validate='key',\
                           validatecommand=(vlobcmd,'%d','%S','%P'))
        txtSiteLOB.grid(row=i+1,column=4,sticky=W)
        txtSiteLOB.bind('<KeyRelease>',self.krlob)
        
        # add lock/remove buttons
        if self._imgLocked:
            btnLockUnlock = Button(frm,image=self._imgUnLocked,command=lambda:self.sitelock(i+1))
        else:
            btnLockUnlock = Button(frm,text="U",command=lambda:self.sitelock(i+1))
        btnLockUnlock.grid(row=i+1,column=5,sticky=W)
        if self._imgRemove:
            btnRemove = Button(frm,image=self._imgRemove,command=lambda:self.siteremove(i+1))
        else:
            btnRemove = Button(frm,text="R",command=lambda:self.siteremove(i+1))
        btnRemove.grid(row=i+1,column=6,sticky=W)
        self._txtSites.append([txtSiteTU,txtSiteName,txtSiteLoc,txtSiteLOB,btnLockUnlock,False,btnRemove])

    def _readconf(self):
        """ read in conf file """
        self.config = LobsterConfig()
        try:
            self.config.read('lobster.conf')
        except Exception, e:
            showerror('Error in Preferences',e)
        
    def _initialize(self):
        # set date/time entries
        n = dt.datetime.utcnow()
        if self.config.ui['dtime'] == 'local': n = z2l(n,self.config.ui['z2l'])
        self.txtSOIDate.insert(0,n.date().strftime("%Y-%m-%d"))
        self.txtSOITU.insert(0,n.time().strftime("%H%M"))
        self._curFile = None
        self._sois = {}
        self._nSOI = 1
        self.master.title("LOBster v%s" % __version__)

    def _validate(self):
        """ processes entries, return a SOI if all are valid, otherwise None """
        soi = SOI()
        for i in range(NUM_SITES):
            # using i+1 in showerror fct results in concat error, so do it here
            n = i+1
            
            # only add a site if all fields have entries and each entry is valid
            tu = self._txtSites[i][SITE_TU].get()
            name = self._txtSites[i][SITE_NAME].get()
            loc = self._txtSites[i][SITE_LOC].get()
            lob = self._txtSites[i][SITE_LOB].get()

            if tu and name and loc and lob:
                try:
                    lob = float(lob)
                    if lob < 0 or lob >= 360:
                        showerror('Invalid LOB',"Site %d LOB must be 0 <=> 360" % n)
                        continue
                    if len(name) == 0 or len(name) > 5:
                        showerror('Invalid Name',"Site %d must be 1 to 5 characters" % n)
                        continue
                    if not validMGRS(loc):
                        showerror('Invalid Location',"Site %d has invalid location entry" % n)
                        continue
                    dt.datetime.strptime(tu,"%H%M")
                except ValueError, e:
                    showerror('Invalid LOB','Site %d LOB must be numeric' % n)
                    continue
                except Exception, e:
                    showerror('Invalid Date/Time','Site %d, date is invalid' % n)
                    continue
                else:
                    # convert lob if necessary to true north before saving to soi
                    if self.config.ui['azimuth'] != 'true':
                        lob = convertazimuth(self.config.ui['azimuth'],'true',lob,self.config.declination)
                    
                    # convert time if necessary to zulu before saving
                    dtg=dt.datetime.strptime(self.txtSOIDate.get()+" "+tu,"%Y-%m-%d %H%M")
                    if self.config.ui['dtime'] == 'local': dtg=l2z(dtg,self.config.ui['z2l'])
                    
                    # add the site
                    try:
                        soi.addsite(name,dtg,loc,lob)
                    except KeyError, e:
                        showerror('Duplicate Site','Site %s already exists, skipping...' % e)

        # exit if no sites were added
        if len(soi.sites) == 0:
            showerror('Invalid Sites','There must be at least one site entered')
            return None
        
        # add dtg, rf, gist and callsign indexes
        try:
            # convert time to zulu if necessary
            dtg = dt.datetime.strptime(self.txtSOIDate.get()+" "+\
                                       self.txtSOITU.get(),"%Y-%m-%d %H%M")
            if self.config.ui['dtime'] == 'local': dtg = l2z(dtg,self.config.ui['z2l'])
            soi.setdtg(dtg)
            soi.setrf(float(self.txtSOIRF.get()))
            gist = self.txtGist.get('1.0',END)
            tags = self.txtGist.tag_ranges("cs")
            for k in xrange(0,len(tags)-1,2):
                soi.addcallsign(self.txtGist.get(tags[k],tags[k+1]),\
                                str(tags[k]),str(tags[k+1]))
            opnote = self.txtOpNote.get('1.0',END)
            soi.setgist(gist)
            soi.setopnote(opnote)
            return soi
        except:
            showerror('Invalid SOI','SOI parameters are incorrect')
            return None

    def _save(self,fpath):
        """ saves data to file fpath """
        try:
            fout = open(fpath,'wb')
            
            # write current sites, locked state and dtg info, then internal data
            sites = []
            for i in range(NUM_SITES):
                if self._txtSites[i][SITE_TU].get() == "": break
                # convert time to zulu if necessary
                dtg = dt.datetime.strptime(self.txtSOIDate.get()+" "+\
                                           self._txtSites[i][SITE_TU].get(),\
                                           "%Y-%m-%d %H%M")
                if self.config.ui['dtime'] == 'local': dtg = l2z(dtg,self.config.ui['z2l'])
                sites.append([dtg.time().strftime("%H%M"),\
                              self._txtSites[i][SITE_NAME].get(),\
                              self._txtSites[i][SITE_LOC].get(),\
                              self._txtSites[i][SITE_LOCKED]])
            pickle.dump(sites,fout)
            
            # and internal
            pickle.dump(self._nSOI,fout) 
            pickle.dump(self._sois,fout)
            fout.close()
            return True
        except Exception,e:
            return e

    def _addgreen6(self,k,s):
        """ adds soi to the green 6 list """       
        if type(s) == type(Convo(None,None,None,None)):
            # Convo
            # convert dtg if nessary 
            dtg = self._sois[s.sender].getdtg()
            if self.config.ui['dtime'] == 'local': dtg = z2l(dtg,self.config.ui['z2l'])
            
            # and compile participating sites
            sites = []
            for skey in s.keys:
                for site in self._sois[skey].sites.keys():
                    if not site in sites: sites.append(site)
            
            # add the convo
            self.g6.add(k,itemtype=IMAGETEXT,image=self._imgG6Convo,text=k)
            self.g6.item_create(k,1,itemtype=IMAGETEXT,text=":".join(sites))
            self.g6.item_create(k,2,itemtype=IMAGETEXT,text=dtg.time().strftime("%H%M"))
            self.g6.item_create(k,3,itemtype=IMAGETEXT,text=self._sois[s.sender].rf)
            self.g6.item_create(k,4,itemtype=IMAGETEXT,text="Mult") 
        else:
            # SOI
            # convert dtg if necessary
            dtg = s.getdtg() # convert time to local if necessary
            if self.config.ui['dtime'] == 'local': dtg = z2l(dtg,self.config.ui['z2l'])
            
            # add the soi 
            self.g6.add(k,itemtype=IMAGETEXT,image=self._imgG6SOI,text=k)
            self.g6.item_create(k,1,itemtype=IMAGETEXT,text=":".join(s.sites))
            self.g6.item_create(k,2,itemtype=IMAGETEXT,text=dtg.time().strftime("%H%M"))
            self.g6.item_create(k,3,itemtype=IMAGETEXT,text=s.rf)
            self.g6.item_create(k,4,itemtype=IMAGETEXT,text=s.df.status)

    def _closefile(self):
        """ close file, resets curFile and deletes everything"""
        # delete internal data
        self._sois = {}
        
        # delete all site info, set lock status to unlocked
        for i in range(NUM_SITES):
            self._clearsiterow(i)
            self._clearsiterow(i)
        
        # clear date, tu, gist, rf and soi records
        self.txtSOIDate.delete(0,END)
        self.txtSOITU.delete(0,END)
        self.txtSOIRF.delete(0,END)
        self.txtGist.delete("1.0",END)
        self.txtOpNote.delete("1.0",END)
        self.g6.delete_all()

    def _filestatus(self,hasChanged):
        """ file is saved or has unsaved changes """
        self._hasChanged = hasChanged
        if not self._curFile:
            if self._hasChanged:
                self.master.title("LOBster Untitled*")
            else:
                self.master.title("LOBster v%s" % __version__)
        else:
            if self._hasChanged:
                self.master.title("LOBster (%s)*" % os.path.split(self._curFile)[1].split('.')[0])
            else:
                self.master.title("LOBster (%s)" % os.path.split(self._curFile)[1].split('.')[0])

## VALIDATION METHODS

    ####
    # validations methods will expect
    #   ac -> action code one of {0=deletion, 1=insertion, -1=focus}
    #   char -> character if any being inserted
    #   txt -> the value the text will have if change is allowed
    
    def _validdate(self,ac,char,txt):
        """ determines if txt is a valid date """
        if ac == '0': return True
        elif ac == '1':
            if len(char) == 1:
                # only digits and '-'
                if char in CHKDATE: return True
                else: return False
        return True
        
    def _validtime(self,ac,char,txt):
        """ determines if t is a valid time """
        if ac == '0': return True
        elif ac == '1':
            if len(char) == 1:
                # only digits, no more than four
                if len(txt) > 4: return False
                if char in CHKINT: return True
                else: return False
        return True

    def _validrf(self,ac,char,txt):
        """ determines if txt is a valid rf """
        if ac == '0': return True
        elif ac == '1':
            if len(char) == 1:
                # only digits or a '.'
                if char in CHKFLOAT: return True
                else: return False
        return True

    def _validname(self,ac,char,txt):
        """ determines if txt is a valid site name """
        if ac == '0': return True
        elif ac == '1':
            if len(char) == 1:
                # name cannot be more than 5 char and is alphanumeric
                if len(txt) > 5: return False
                if char in CHKALNUM: return True
                else: return False
            else:
                if len(txt) > 5: return False    
        return True

    def _validlocation(self,ac,char,txt):
        """ determines if t is a valid time """
        if ac == '0': return True
        elif ac == '1':
            if len(char) == 1:
                # location cannot be more than 15 char and is alphanumeric
                if len(txt) > 15: return False
                if char in CHKALNUM: return True
                else: return False
            else:
                if len(txt) > 15: return False    
        return True

    def _validlob(self,ac,char,txt):
        """ determines if txt is a valid lob """
        if ac == '0': return True
        elif ac == '1':
            if len(char) == 1:
                # only digits or a '.' dissallow more than 5 characters
                if len(txt) > 5: return False
                if char in CHKFLOAT: return True
                else: return False
        return True

## OPEN DIALOG METHODS

    def _adddialog(self,name,dialog):
        """ adds the dialog object dialog having key name to dialogs """
        self._dialogs[name] = dialog

    def _deletedialog(self,name):
        """ delete the dialog with name and remove it from the list """
        self._dialogs[name].tk.destroy()
        del self._dialogs[name]

    def _deletedialogs(self,desc):
        """ deletes all dialogs with desc """
        opened = self.getdialogs(desc,False)
        for dialog in opened: dialog.pnl.close()

    def _getdialog(self,desc,pnlOnly=True):
        """ returns the first dialog panel with desc or None """
        for dialog in self._dialogs:
            if self._dialogs[dialog].desc == desc:
                if pnlOnly:
                    return self._dialogs[dialog].pnl
                else:
                    return self._dialogs[dialog]
        return None

    def _getdialogs(self,desc,pnlOnly=True):
        """ returns all dialog panels with desc or [] if there are none open """
        opened = []
        for dialog in self._dialogs:
            if self._dialogs[dialog].desc == desc:
                if pnlOnly:
                    opened.append(self._dialogs[dialog].pnl)
                else:
                    opened.append(self._dialogs[dialog])
        return opened

    def _hasdialog(self,desc):
        """ returns True if there is at least one dialog with desc """
        for dialog in self._dialogs:
            if self._dialogs[dialog].desc == desc: return True
        return False

    def _closedialogs(self,forceall=False):
        """ notifies all open dialogs to close """
        dialogs = self._dialogs.keys()
        for dialog in dialogs:
            if forceall or self._dialogs[dialog].forceClose:
                self._dialogs[dialog].pnl.closeapp()

#### start the program
def main():
    # a green 6 (.g6) file can be passed on the command line
    t = Tk()
    fpath = None
    if len(sys.argv) == 2: fpath = sys.argv[1]
    LobsterRTPanel(t,fpath).mainloop()

if __name__ == '__main__': main()
