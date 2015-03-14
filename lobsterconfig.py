#!/usr/bin/env python
from configobj import ConfigObj
from configobj import ParseError

__name__ = 'lobsterconfig'
__version__ = '0.0.1'
__revdate__ = 'October 2013'
__author__ = 'Dale Paterson'

#### exceptions ####
class ConfigException(Exception): pass                          # generic config
class ConfigWriteException(ConfigException): pass               # conf file write failure
class ConfigReadException(ConfigException): pass                # conf file read failure
class ConfigParseException(ConfigReadException): pass           # failure to parse
class ConfigRequiredSectionException(ConfigReadException): pass # missing required section
class ConfigRequiredParamException(ConfigReadException): pass   # lacking required parameters
class ConfigInvalidParamException(ConfigReadException): pass    # invalid parameter

class LobsterConfig(object):
    """ Reads/Writes config file for LOBster initialization """
    def __init__(self,config=None):
        self._default()
        if config: self.read(config)

    def read(self,config):
        """ read and validate a .conf and set internals """
        # initialize configobj with conf file
        try:
            conf = ConfigObj(config)
        except ParseError, e:
            raise ConfigParseException, e
        
        # check for sections
        try:
            d = conf['DECLINATION']
            g = conf['GEO']
            u = conf['UI']
        except KeyError, e:
            raise ConfigRequiredSectionException, "Section %s missing" % e
        
        # DECLINATION: decl must be easterly or westerly. gtom and ttom are floats
        # betw/ 0 and 360
        try:
            decl = d['direction']  
            g2m = float(d['gtom'])
            g2t = float(d['gtot'])
            if not (decl == 'westerly' or decl == 'easterly'): raise ConfigInvalidParamException, "direction"
            if g2m < 0 or g2m >= 360: raise ConfigInvalidParamException, "G-M"
            if g2t < 0 or g2t >= 360: raise ConfigInvalidParamException, "G-T" 
            # all good set them
            self.declination['decl'] = decl
            self.declination['g2m'] = float(d['gtom'])
            self.declination['g2t'] = float(d['gtot']) 
        except KeyError, e:
            raise ConfigRequiredParamException, "Parameter %s missing" % e
        except Exception, e:
            raise ConfigInvalidParamException, e
        
        # GEO: ellipse is a string, threshold a int
        # TODO: ensure ellipse is one of allowed strings
        try:
            self.geo['ellipse'] = g['ellipse']
            self.geo['cutt'] = int(g['cut_threshold'])
        except KeyError, e:
            raise ConfigRequiredParamException, "Parameter %s missing" % e
        except Exception, e:
            raise ConfigInvalidParamException, e
        
        # UI: azimuth is one of true,grid,magnetic local diff is float and 
        # display time is local or zulu
        try:
            a = u['azimuth']
            a = a.lower()
            if not (a == "true" or a == "grid" or a == "magnetic"):
                raise ConfigInvalidParamException, "Bearings must be in true, grid or magnetic"
            d = u['display_time']
            d = d.lower()
            if not (d == 'local' or d == 'zulu'):
                raise ConfigInvalidParamException, "Display time must be local or zulu"
            self.ui['azimuth'] = a
            self.ui['z2l'] = float(u['local_diff'])
            self.ui['dtime'] = d
        except KeyError, e:
            raise ConfigRequiredParamException, "Parameter %s missing" % e
        except Exception, e:
            raise ConfigInvalidParamException, e
        
    def write(self,config):
        """ write to a .conf file expects to be valid """
        # make an empty config object
        conf = ConfigObj()
        conf.filename = config
        
        # set parameters
        conf['DECLINATION'] = {'direction':self.declination['decl'],\
                               'gtom':self.declination['g2m'],\
                               'gtot':self.declination['g2t']}
        conf['GEO'] = {'ellipse':self.geo['ellipse'],\
                       'cut_threshold':self.geo['cutt']}
        conf['UI'] = {'azimuth':self.ui['azimuth'],\
                      'local_diff':self.ui['z2l'],\
                      'display_time':self.ui['dtime']}
        
        # write it
        try:
            conf.write()
        except Exception, e:
            raise ConfigWriteException, "Failed to write %s: %s" % (config,e)
        
    #### PRIVATE FCTS ####
    def _default(self):
        """ initializes internal to default configuation """
        self.declination = {'decl':'easterly','g2m':3,'g2t':1}
        self.geo = {'ellipse':'WGS84','cutt':100}
        self.ui = {'azimuth':'true','z2l':4.5,'dtime':'zulu'}
