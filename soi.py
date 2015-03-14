#!/usr/bin/env python
""" soi.py: defines signals of interest

 soi - Defines several classes (primary is soi) used to describe a collection
 of sites and lobs to emitters of interest
"""
import itertools                                     # for permutations
import math                                          # for isnan,isinf
from landnav import findcut                          # cut fct for pairs of pts
from landnav import _GEOD
from landnav import _MGRS


__name__ = 'soi'
__license__ = 'GPL v3.0'
__version__ = '0.2.9'
__date__ = 'December 2013'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

# GLOBALS
CUT_THRESHOLD = 100 # max dist in meters to identify a cut

class Site(object):
    """
     A Site has a 5 letter name, a time up (dtg the site was up and running),
     a location (in MGRS) and a lob (bearing to an emitter). 
    """
    def __init__(self,name,tu,location,lob):
        self.name=name
        self.tu=tu
        self.location=location
        self.lob=lob

# DF STATES
DF_INVALID = -1
DF_NONE    =  0
DF_LOB     =  1
DF_CUT     =  2
DF_AMB_CUT =  3
DF_FIX     =  4

# CUT INDICES
DF_CUT_ANAME = 0
DF_CUT_ALOC  = 1
DF_CUT_ALOB  = 2
DF_CUT_BNAME = 3
DF_CUT_BLOC  = 4
DF_CUT_BLOB  = 5
DF_CUT_X     = 6
DF_CUT_ADIST = 7
DF_CUT_BDIST = 8

class DF(object):
    """
     record for a set of cuts given 1 or more points and corresponding bearings
      - cuts is a list of tuples (nameA,locA,bearingA,nameB,locationB,bearingB,
        locationcut,distA,distB)
     where ptA and ptB are MGRS locations, bA and bB are respective lobs. 
     ptcut is a grid designator or (Inf,Amb,None) if there is a cut from A & B 
     and distA and distB are distances (in meters) or Inf from points A & B 
     respectively
      - state identifies the result of the df and is one of:
         DF_INVALID - no df, no points and lobs have been given
         DF_NONE - all cuts are ambiguous, infinite or none
         DF_LOB - only one site has been entered or only one site has a lob
         DF_CUT - a cut but no fix
         DF_AMB_CUT - (ambiguous cut) two or more differing cuts
         DF_FIX - a possible fix has been identified
     NOTE: we only calculate cuts. Every pairing of points and corresponding 
      bearings are used to calculate a list of cuts
    """
    def __init__(self):
        #self.centroid = None
        self.fix = None
        self.cuts = []
        self.dists = []
        self.avgDist = float('inf')
        self.state = DF_INVALID
        self.status = ""
        
#### ACCESSORS ####

    def getcut(self,ptA,ptB):
        """ 
         returns the cut between ptA and ptB (where each is a name of the site)
        """
        for cut in self.cuts:
            if cut[DF_CUT_ANAME] == ptA and cut[DF_CUT_BNAME] == ptB:
                return cut[DF_CUT_X]
            elif cut[DF_CUT_ANAME] == ptB and cut[DF_CUT_BNAME] == ptA:
                return cut[DF_CUT_X]
        return None
    
#### TRIANGULATION ####
    
    def find(self,pts,delta):
        """
         find cuts (if any) between all pairings of pts and using the threshold
         delta determines if each found cut is within the max distance
        """
        # get all possible pairings (where (a,b) = (b,a) and excluding (a,a))
        for combos in list(itertools.combinations(range(len(pts)),2)):
            ptA = pts[combos[0]]                  # first pt
            ptB = pts[combos[1]]                  # second pt
            lla = _MGRS.toLatLon(ptA[1])          # convert to lat lon
            llb = _MGRS.toLatLon(ptB[1])          # convert to lat lon
            llx = findcut(lla,ptA[2],llb,ptB[2])  # triangulate
            if type(llx) == type((0,1)):
                # NOTE: geod.inv goes lon,lat in argument pairs ignore the first 
                # two return values which are azimuth, back azimuth
                ptX = _MGRS.toMGRS(llx[0],llx[1])
                da = _GEOD.inv(lla[1],lla[0],llx[1],llx[0])[2]
                db = _GEOD.inv(llb[1],llb[0],llx[1],llx[0])[2] 
            else:
                da = -1
                db = -1
                if math.isinf(llx):
                    ptX = "Inf"
                elif math.isnan(llx):
                    ptX = "Amb"
                else:
                    ptX = "None"
            
            # append to cuts
            # cuts is a list of tuples 
            # (nameA,ptA,bA,nameB,ptB,bB,ptCut,distA,distB)
            self.cuts.append((ptA[0],ptA[1],ptA[2],ptB[0],ptB[1],ptB[2],ptX,da,db))
                     
        self._deconflict(pts,delta)

#### PRIVATE FUNCTIONS ####

    def _deconflict(self,pts,delta):
        """
         attempts to make sense of multiple cuts if possible, identify a cut
         and set the DF state
        """
        self.status = "None"
        if len(pts) == 1:
            # only 1 point, we have a LOB
            self.state = DF_LOB
            self.status = "LOB %s->%.0f" % (pts[0][0],pts[0][2])
        elif len(pts) == 2:
            # only 2 points, we have either a valid cut or two lobs
            if self._validcut(self.cuts[0][DF_CUT_X]):
                self.state = DF_CUT
                self.status = "CUT %s<->%s %s" % (pts[0][0],pts[1][0],self.cuts[0][DF_CUT_X])
            else:
                self.state = DF_LOB
                self.status = "LOB(s)"
        else:
            # three or more cuts - get the centroid
            self.fix = self._centroid()

            # sum the number of valid cuts, number of invalid and get
            # distances bewteen each cut and the centroid
            nV = 0
            nNaN = 0
            for cut in self.cuts:
                # tally valid
                if self._validcut(cut[DF_CUT_X]): nV += 1
                
                # compile distances
                if not self._validcut(cut[DF_CUT_X]):
                    self.dists.append(float('NaN'))
                    nNaN += 1
                else:
                    llpt = _MGRS.toLatLon(cut[DF_CUT_X])
                    llc = _MGRS.toLatLon(self.fix)
                    dist = _GEOD.inv(llpt[1],llpt[0],llc[1],llc[0])[2]
                    self.dists.append(dist)
            
            # if every distance was NaN we do not have a fix
            if nNaN == len(self.dists):
                self.state = DF_NONE
                self.status = "No Cuts"
            else:
                # find average distance
                # NOTE: any inf will result in dist of inf, meaning we 
                # may have cuts but no fix
                self.avgDist = sum(self.dists) / len(self.dists)
                if self.avgDist < delta:
                    # the fix is the centroid
                    self.state = DF_FIX
                    self.status = "FIX %s" % self.fix
                else:
                    # note we save the centroid
                    self.state = DF_AMB_CUT
                    self.status = "CUT(s)"

    def _validcut(self,cut):
        """ returns true if cut is valid, false otherwise """
        if cut == 'Inf': return False
        if cut == 'Amb': return False
        if cut == 'None': return False
        return True

    def _centroid(self):
        """ finds the centroid """
        # we consider each cut as a point in a polygon taking 
        # the centroid, center of the polygon will guestimate the fix
        lats = 0
        lons = 0
        for cut in self.cuts:
            (lat,lon) = _MGRS.toLatLon(cut[DF_CUT_X])
            lats += lat
            lons += lon
        lats /= len(self.cuts)
        lons /= len(self.cuts)
        return _MGRS.toMGRS(lats,lons)

class SOI(object):
    """
     SOI, the primary class. An SOI describes an emitter, a signal with
     an RF, Time Up and gist and 1 or more sites, cuts and callsigns. 
     NOTE: as an emitter, the SOI is a single source, i.e. one side of a 
           conversation. At present, there is no means to identify, multiple 
           emitters involved in a single conversation
     NOTE: pushed down location in Tix Text in callsigns, don't like it but
           it was easiest this way however, nonportable across gui platforms
    """
    def __init__(self):
        self.sites = {}
        self.pri = []
        self.df = None
        self.dtg = None
        self.rf = None
        self.gist = ""
        self.callsigns = []
        self.opnote = ""

#### METHODS ####

    def triangulate(self,delta=CUT_THRESHOLD):
        """ attempts to find a df of the soi given the threshold delta """
        sites = []
        for site in self.sites.values(): sites.append((site.name,site.location,site.lob))
        
        if sites:
            self.df = DF()
            self.df.find(sites,delta)

#### ACCESSORS ####

    def addsite(self,name,tu,location,lob):
        """ 
         adds a site if it doesn't already exist, sites are prioritized by the
         order they are added
        """
        if self.sites.has_key(name): raise KeyError, name
        self.pri.append(name)
        self.sites[name]=Site(name,tu,location,lob) 
    def addcallsign(self,cs,s,e): self.callsigns.append((cs,s,e))
    def setdtg(self,dtg): self.dtg=dtg
    def setrf(self,rf): self.rf=rf
    def setgist(self,gist): self.gist=gist
    def setopnote(self,o): self.opnote=o
    def getsite(self,site): return self.sites[site]
    def getrf(self): return self.rf
    def getdtg(self): return self.dtg
    def getdate(self): return self.dtg.date()
    def gettu(self): return self.dtg.time()
    def getgist(self): return self.gist
    def getcallsigns(self,csOnly=False):
        if csOnly:
            ret = []
            for cs in self.callsigns: ret.append(cs[0])
            return ret
        else:
            return self.callsigns
    def getuniquecallsigns(self):
        ret = []
        for cs in self.callsigns:
            if cs[0] not in ret: ret.append(cs[0])
        return ret
    def getopnote(self): return self.opnote

