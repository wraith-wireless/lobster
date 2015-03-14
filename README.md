![](img/lobster-logo2.png?raw=true)
# LOBster: a Low-level Voice Intercept signal editor for near real-time VHF communications tracking.

## 1 DESCRIPTION:
LOBster was designed to alleviate errors in DFing inherent in human plotting
specifically on maps of 1:50000 by attempting to siimplify the collation of
multiple LOBs from one or more non-colocated collection sites. The next logical
evolution which I have not got around to developing is to use gps devices to
ascertain the current position (allowing sites to move without manually entering
the new location) and to implement an adhoc wireless network facilitating the
entry of LOBs from other sites without require some external communication method
and manual entry.

This program as is has been tested and applied in real-world situations with
success.

## 2. REQUIREMENTS: 
 * linux (preferred 3.x kernel) tested on Ubuntu 12.04 and 14.04
 * Python 2.7
 * Tix 8.4.3, tk, tk-dev
 * mgrs 1.1
 * matplotlib 1.3.1 (Note: after updating to matplotlib 1.4.3, basemap 'broke'
   and had to fall back to older version
   NOTE:
   to use images map window, take the *.ppm files
    erase.ppm  labels.ppm  quadrant.ppm  separator.ppm
   located in img/navbar & copy to /usr/share/matplotlib/mpl-data/images
 * basemap 1.07