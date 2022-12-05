######################################################
#          BLENDER TO LIGHTFLOW EXPORTER             #
#----------------------------------------------------#
#    ORIGINAL SCRIPT BY Jaan Oras a.k.a. 'Montz'     #
# MODIFICATIONS BY Alfredo de Greef a.k.a. 'Eeshlo'  #
#       GUI BY Stefano Selleri a.k.a. 'S68'          #
######################################################
#                                                    #
# JUST PRESS ALT+P, nothing to change in the script  # 
#                                                    #
######################################################


# Get the Blender version and import the necessary modules
import Blender
BL_VERSION = Blender.Get('version')
if BL_VERSION<=223:
    import Blender210, GUI  # only available in versions <= 223

# Enable(1) or Disable(0) full trace print for debugging, as with normal python use
# also used as flag to print mesh info
# since this is not accesible for anyone else but me, traceback is only imported here when PRINT_TRACE is set, not in START() anymore
PRINT_TRACE = 1
if PRINT_TRACE: import traceback

# import all need modules
import os, sys, webbrowser, signal

# it seems the time module causes trouble on Linux again
AUTODISP_OK = 0
try:
    import time
    AUTODISP_OK = 1

except:
    print "Can't import time module, autodisplay disabled"
    AUTODISP_OK = 0

# array module, in case anyone else on Linux had the same problems as me, better catch it
ARMOD = 0
try:
    import array
    ARMOD = 1

except ImportError:
    ARMOD = 0
    
from Blender import Draw, BGL
from math import *
from struct import pack, unpack

# OpenGL extensions (not in Blender.BGL) to handle RGB<->BGR
GL_BGR_EXT, GL_BGRA_EXT = 0x80e0, 0x80e1
# first find out if this is actually supported by the OpenGL driver
fast_display_ok = ('GL_EXT_bgra' in BGL.glGetString(BGL.GL_EXTENSIONS).split())
if fast_display_ok:
    # yes, it is...
    print "Fast display,",
    DISPLAY_MODES = {3: GL_BGR_EXT, 4: GL_BGRA_EXT}
else:
    # not supported, software fallback...
    print "Slow display,",
    DISPLAY_MODES = {3: BGL.GL_RGB, 4: BGL.GL_RGBA}
if ARMOD:
    print "array"
else:
    print "no array"


# try to import win32 modules
MSPOK = 0
W32PI = 0
if sys.platform=='win32':

    import msvcrt   # keyboard handling for automatic display
    def keypressed():
        if msvcrt.kbhit():
            msvcrt.getch()
            return 1

    # new module to get simple process information for win32, not needed for Linux
    if BL_VERSION<=228:
        try:
            import win32procinfo
            W32PI = 1
        except ImportError:
            print "win32procinfo module not found"
            W32PI = 0
    
        ## another new module to directly import MATSpider materials, only available in Windows
        try:
            import MSPint
            MSPOK = 1
        except ImportError:
            print "MSPint module not found"
            MSPOK = 0
    

else:
    # linux detect keypress, might not work for everybody,
    # only returns true when pressing enter-key, the pressed key before that is read to clear stdin

    # update: completely forgot, it does seem to be missing from default python installs, so catch...
    # only try to import if previous needed module imports succeeded

    if AUTODISP_OK:
        try:
            from select import select

        except ImportError:
            AUTODISP_OK = 0
        else:
            def keypressed():
                if len(select([sys.stdin], [], [], 0)[0]):
                    sys.stdin.read(1)
                    return 1

# try to import texture conversion module, both platforms
TOTGA_OK = 0
try:
    import totga
    TOTGA_OK = 1
    
except ImportError:
    print "totga module not found, texture conversion not possible!"
    TOTGA_OK = 0


# TRY TO IMPORT BLENDFILE READER
try:
    from BFREAD import *
    BFREAD_OK = 1

except:
    print "Could not import Blendfile reader"
    BFREAD_OK = 0

# ID used for path settings file
LFE_ID = "249.0"


####################################################################
# INTERFACE GLOBALS these are all saved in the scene settings file #
####################################################################

# FOR PATH INPUT
LFE_paths_filename  =   ".LFE_paths"
LFE_scene_filename  =   ".LFE_scene"
LFE_scene_filepath  =   ""
Tpath       = Draw.Create("")
TLFpath     = Draw.Create("")
TMPpath     = Draw.Create("")
Tsave_path  = Draw.Create(0)
# (path+) Editor name
Teditpath   = Draw.Create("")
# MATSpider main directory
Tmsp_path   = Draw.Create("")
# TEXTURE DIRECTORY
Ttex_dir    = Draw.Create("")
# LINUX ONLY, BROWSER PREFERENCE
Tbrowser    = Draw.Create(0)    # default

######################################################
# GUI EVENT NUMBERS                                  #
######################################################

evt_exit        =   1
evt_ignore      =   2
evt_export      =   3
evt_world       =   4
evt_reset       =   5
evt_save        =   6
evt_rendscr     =   7
evt_settscr     =   8
evt_STARTLF     =   9
evt_display     =   10
evt_fsel        =   11
evt_pytest      =   12
evt_pyedit      =   13
evt_anim        =   14
evt_eranim      =   15
evt_tested      =   16
evt_testmsp     =   17
evt_MSPMATWIN   =   18
evt_MSPLIBWIN   =   19
evt_imgdof      =   20
evt_dofmet      =   21
evt_halomutex   =   22
evt_glitmutex   =   23
evt_fseltex     =   24
evt_morpar      =   25
evt_preset      =   26
evt_shoDOCS     =   27
evt_redefpref   =   28
evt_ptcancel    =   29
evt_imgsize     =   30
evt_layerwin    =   31
evt_alloff      =   32
evt_allon       =   33
evt_KILL        =   34
evt_TGredraw    =   35
evt_testbrowser =   36

######################################################
# GLOBALS                                            #
######################################################
sl = os.sep
sfilepath = ""
LFHOME = sl+"lightflow"
LFTEMP = LFHOME+sl+"LFtemp"
LFXPORT = LFHOME+sl+"LFexport" # THE MOST IMPORTANT VARIABLE
outname = ""
outdir = ""
file = None
meshfile = None
matfile = None
pyname = ""
pyfilepath = ""
#PYPATH = os.environ['PYTHONPATH']
PYPATH = ""
frame_outname = ""
texnames = {}
matnames = []
# for animation results
imgdir = ""
# for converted textures
tgatex_dir = ""
# for all data
alldata_dir = ""

anim_indent = ''    # indentation offset for animation script

### Short reference to progressbar function
## jms : modif for 228
if BL_VERSION<228:
   pbar = Blender.Window.draw_progressbar
else:
   pbar = Blender.Window.DrawProgressBar
## jms : modif for 228

   
### Status display
WORKING = 0
EXPORT_FAILED = 0   # could happen...

### Path GUI
PATH_TITLE = ""
# PYTHONPATH NOW USED TO SET UP THE PATH TO PYTHON EXECUTABLE
Tpy_execpath    =   Draw.Create('Tpy_exe')
# File selector not in versions >223
if BL_VERSION<=223:
    FSEL = GUI.FileSelector()

MSP_PATHOK = [0, "MATSpider path not correct"]
MSP_PATH = ""
# The texture image directory,
TEXROOT = ""
# WHEN CALLED FROM MAIN GUI, DRAW EXTRA 'CANCEL' BUTTON
PREF_CANCEL = 0

### Render GUI
RENDER_STARTED = 0
NO_FILES = 1
TGA = None
REND_MSG = 'Ready!'
# Python process ID(lix)/Handle(win)
# start with -1 so the script won't say Lightflow is done, bacause it cannot determine that yet
LFPID = -1

# MESH DATA STRINGS
mesh_hdr_str = ''
mesh_dat_str = ''
# CURRENT MAIN MESH, used to make sure that the mesh is 'GetRawed' only the first time for multiple materials
CURRENT_MESH = None

# used to warn user that no export layer is set
LAYER_ERR = 0


# Difficult bit for advanced users, who can look beyond the 'This looks like programming!' impression
# Although I wouldn't be surprised if it isn't used at all...
# In the script however it is also used to have access to the correct names for materials in different Blender versions
if BL_VERSION<=223:
    MSP_BL_VARS = { 'BLEND_ALPHA':'Alpha', 'BLEND_AMB':'Amb',
                'BLEND_COLOR_RGB':'ColRGB', 'BLEND_COLOR_R':'R', 'BLEND_COLOR_G':'G', 'BLEND_COLOR_B':'B',
                'BLEND_EMIT':'Emit', 'BLEND_HARD':'Hard',
                'BLEND_COLOR_MIR_RGB':'MirRGB', 'BLEND_COLOR_MIR_R':'MirR', 'BLEND_COLOR_MIR_G':'MirG', 'BLEND_COLOR_MIR_B':'MirB',
                'BLEND_REF':'Ref', 'BLEND_SPTRA':'SpTra', 'BLEND_SPEC':'Spec',
                'BLEND_COLOR_SPEC_RGB':'SpecRGB', 'BLEND_COLOR_SPEC_R':'SpecR', 'BLEND_COLOR_SPEC_G':'SpecG', 'BLEND_COLOR_SPEC_B':'SpecB',
                # only used for 'translation'
                'BLEND_MATMODE': 'Mode' }
elif BL_VERSION<=223:
    # Publisher naming differences, some can still be used as is, but in general all should start with lowercase letter
    # Side note: both spec and hard can't be set beyond 1.0 & 128 respectively (from python), and there seem to be more bugs in 225 as well
    MSP_BL_VARS = { 'BLEND_ALPHA':'alpha', 'BLEND_AMB':'amb',
            'BLEND_COLOR_RGB':'ColRGB', 'BLEND_COLOR_R':'R', 'BLEND_COLOR_G':'G', 'BLEND_COLOR_B':'B',
            'BLEND_EMIT':'emit', 'BLEND_HARD':'hard',
            'BLEND_COLOR_MIR_RGB':'MirRGB', 'BLEND_COLOR_MIR_R':'mirR', 'BLEND_COLOR_MIR_G':'mirG', 'BLEND_COLOR_MIR_B':'mirB',
            'BLEND_REF':'ref', 'BLEND_SPTRA':'specTransp', 'BLEND_SPEC':'spec',
            'BLEND_COLOR_SPEC_RGB':'SpecRGB', 'BLEND_COLOR_SPEC_R':'specR', 'BLEND_COLOR_SPEC_G':'specG', 'BLEND_COLOR_SPEC_B':'specB',
            # only used for 'translation'
            'BLEND_MATMODE': 'mode' }

## jms : modif for 228
elif BL_VERSION>=228:
    MSP_BL_VARS = { 'BLEND_ALPHA':'alpha', 'BLEND_AMB':'amb',
            'BLEND_COLOR_RGB':'ColRGB', 'BLEND_COLOR_R':'R', 'BLEND_COLOR_G':'G', 'BLEND_COLOR_B':'B',
            'BLEND_EMIT':'emit', 'BLEND_HARD':'hard',
            'BLEND_COLOR_MIR_RGB':'MirRGB', 'BLEND_COLOR_MIR_R':'mirCol[0]', 'BLEND_COLOR_MIR_G':'mirCol[1]', 'BLEND_COLOR_MIR_B':'mirCol[2]',
            'BLEND_REF':'ref', 'BLEND_SPTRA':'specTransp', 'BLEND_SPEC':'spec',
            'BLEND_COLOR_SPEC_RGB':'SpecRGB', 'BLEND_COLOR_SPEC_R':'specCol[0]', 'BLEND_COLOR_SPEC_G':'specCol[1]', 'BLEND_COLOR_SPEC_B':'specCol[2]',
            # only used for 'translation'
            'BLEND_MATMODE': 'mode' }
## jms : modif for 228
    
# ipo only data
MSP_BL_VARS_IPO = { 'BLEND_OFS_XYZ':'OfsXYZ', 'BLEND_OFS_X':'OfsX', 'BLEND_OFS_Y':'OfsY', 'BLEND_OFS_Z':'OfsZ',
                'BLEND_SIZE_XYZ':'SizeXYZ', 'BLEND_SIZE_X':'SizeX', 'BLEND_SIZE_Y':'SizeY', 'BLEND_SIZE_Z':'SizeZ',
                'BLEND_TEX_RGB':'TexRGB', 'BLEND_TEX_R':'texR', 'BLEND_TEX_G':'texG', 'BLEND_TEX_B':'texB',
                'BLEND_DVAR':'DefVar', 'BLEND_COL':'Col', 'BLEND_NOR':'Nor', 'BLEND_VAR':'Var'}


# There is an extra variable available that is not in these dictionaries: BLEND_TIME, used for the current frame time,
# for use with smoke/fire for instance, or any other time based effect
# See WRITE_MATSPIDER()

# Toggle button state indication, just to make it more clear
TGSTATE = ["Off", "On"]

# for export/render animation from blender
ANIM_STARTED = 0

# MATSpider material use count
MATSPIDER_USECOUNT = {}

# Blendfile material use count
BLENDFILE_USECOUNT = {}

# SINCE LIGHTFLOW USES GLOBAL TEXTURE COORDINATES,
# NEED TO EXTRACT TEXTURE SPACE BOUNDING BOX FROM MESHES.
# These are in local object space only, the transform handles the rest
TEX_BOUNDS = {}

# WRITE ONCE LF IMAGE TEXTURE LIST
BLENDFILE_LFIMG_LIST = []

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

######################################################
### THE REALLY IMPORTANT MESH 'POINTER' DICTIONARY ###
######################################################

### This dictionary is used to only 'get' (GetRaw, ob.data) mesh data once
### Blender <=223 has big problems with memory which makes it almost impossible to export
### animations unless the meshes are small. Publisher seems to do better in that respect.
# The mesh.data pointer is stored by object name
MESH_PT_DICT = {}

# FOR SIGHANDLER TO PRINT MESSAGE
CTRLC_USED = 0

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


###########################################################
#  SINGLE FILE ANIMATION DATA PACKING & HELPER FUNCTIONS  #
###########################################################

# TOTAL REWRITE, NO MORE ROT, SIZE, LOC, INSTEAD THE MATRIX IS USED DIRECTLY
# EXCEPT FOR THE CAMERA, WHICH IS NOT AFFECTED BY NON-UNIFORM SCALING
# well, it is, but only for the camera shape in Blender, nothing else, this way is easier too.
# Disadvantage is of course that it is ~2 times larger.
# Could use quats, but would need lots of extra code in the python file which would look very 'scary' to the average user...
#-------------------------------------------------------------------------------------------------------------------------------
# FORMAT OF DATA STRING:
# First 4 bytes = long, number of objects (everything included),
# then for every object 16 floats representing the Blender matrix for this object.
# Last is the camera, which is 9 floats but are 3 vectors representing eye, aim & up instead.
# All of these are stored per frame.
# There is no information in the file as to what object the data belongs to,
# the unpack script just expects them to be in a certain order.
# If an object is not animated there is no data for it.
# [..] is optional
# NUMBER OF OBJECTS (long, 4 bytes)
#   FRAME 1
#       OBJECT 1 DATA   matrix, 64 bytes (4*sizeof(vector4)) in order: lamp, arealight, texcontrol, mesh, FOCUS
#       [OBJECT N DATA]
#       CAMERA DATA     3x vector3, 36 bytes (3*sizeof(vector3)): eye, aim, up
#   FRAME N
#       OBJECT 1 DATA
#       [OBJECT N DATA]
#       CAMERA DATA
# and so on...
#                                                                                   objects             camera
# So the number of frames can be calculated with ((len(datastring) - 4) / (((number_of_objects-1) << 6) + 36))


# originally contained more functions than necessary, but the class is kept
class AnimPack:
    def __init__(self):
        self.AnimData = ''

    def PackAllFrames(self, oblist, camname):
        # Main function, returns packed string with animation data
        # oblist should be a list of ALL objects exported, in the order of export: lamps, arealights, texture controllers, meshes, FOCUS
        # camname is the name of the main camera, since this is handled differently
         
        # return if nothing can be done
        if len(oblist)==0: return
         
        # get frame range
        sta = Blender.Get('staframe')
        end = Blender.Get('endframe')
        # just to reset afterwards
        cur = Blender.Get('curframe')
         
        # The packed string
        self.AnimData = ''
         
        # Start with the number of objects
        self.AnimData += pack('l', len(oblist)+1)   # camera counts too!
         
        if BL_VERSION>223:
            curscene = Blender.Scene.getCurrent()
        
        # Now get all matrix data from every object every frame
        for cframe in range(sta, end+1):
         
            # set the current frame, which updates blender so we can get the matrices
            if BL_VERSION<=223 or BL_VERSION>=228:
                Blender.Set('curframe', cframe)
            elif BL_VERSION<228:
                print 6
                curscene.frameSettings(curscene.startFrame(), curscene.endFrame(), cframe)
            else:
                Blender.Set('curframe', cframe)
                
            # Pack the object animation data
            for obname in oblist:
                # Pack matrix for this object at this frame
                bmtx = Blender.Object.Get(obname).matrix
                t = list(bmtx[0])
                t.insert(0, '4f')
                self.AnimData += apply(pack, t)
                t = list(bmtx[1])
                t.insert(0, '4f')
                self.AnimData += apply(pack, t)
                t = list(bmtx[2])
                t.insert(0, '4f')
                self.AnimData += apply(pack, t)
                t = list(bmtx[3])
                t.insert(0, '4f')
                self.AnimData += apply(pack, t)
            
            # now pack the camera data, not matrix but eye, aim & up instead
            cmtx = Blender.Object.Get(camname).matrix
            rot, siz, eye = infoFromMtx(cmtx)
            isy, isz = siz[1], siz[2]
            if isy!=0.0: isy = 1.0/isy
            if isz!=0.0: isz = -1.0/isz
            # look direction
            aim = (eye[0] + cmtx[2][0]*isz, eye[1] + cmtx[2][1]*isz, eye[2] + cmtx[2][2]*isz)
            # up vector
            up = [cmtx[1][0]*isy, cmtx[1][1]*isy, cmtx[1][2]*isy]
            self.AnimData += pack('3f', eye[0], eye[1], eye[2])
            self.AnimData += pack('3f', aim[0], aim[1], aim[2])
            self.AnimData += pack('3f', up[0], up[1], up[2])

        # reset to whatever the frame was when this was first started
        if BL_VERSION<=223 or BL_VERSION>=228:
            Blender.Set('curframe', cur)
        else:
            curscene = Blender.Scene.getCurrent()
            curscene.frameSettings(curscene.startFrame(), curscene.endFrame(), cur)

        return self.AnimData


# function to write the start of the animation script
def WriteAnimScriptStart():
    st = "from struct import pack, unpack\n"
    st += "from math import sqrt\n\n"
    st += "# offset to read the data, actual data starts at 4th byte\n"
    st += "offset = 4\n\n"
    st += "def GetAnimData(iscam=0):\n"
    st += "\tglobal offset\n"
    st += "\tif iscam:\n\t\t# CAMERA EYE, AIM & UP VECTORS\n"
    st += "\t\tdt1 = unpack('3f', animdat[offset:offset+12])\n"
    st += "\t\toffset = offset + 12\n"      # can't use '+=' , might be Py1.5 !
    st += "\t\tdt2 = unpack('3f', animdat[offset:offset+12])\n"
    st += "\t\toffset = offset + 12\n"
    st += "\t\tdt3 = unpack('3f', animdat[offset:offset+12])\n"
    st += "\t\toffset = offset + 12\n"
    st += "\t\treturn dt1, dt2, dt3\n"
    st += "\t# OBJECT MATRIX\n"
    st += "\tdt1 = unpack('4f', animdat[offset:offset+16])\n"
    st += "\toffset = offset + 16\n"
    st += "\tdt2 = unpack('4f', animdat[offset:offset+16])\n"
    st += "\toffset = offset + 16\n"
    st += "\tdt3 = unpack('4f', animdat[offset:offset+16])\n"
    st += "\toffset = offset + 16\n"
    st += "\tdt4 = unpack('4f', animdat[offset:offset+16])\n"
    st += "\toffset = offset + 16\n"
    st += "\treturn [list(dt1), list(dt2), list(dt3), list(dt4)]\n\n"
    st += "# Get the material definitions\n"
    # full paths for material file and animation data, replacing backslashes with forward as always
    GetOutdir()
    st += "matfile = open('%s', 'r')\n" % os.path.join(outdir, 'ANIM_MATERIALS.txt').replace('\\', '/')
    st += "material_string = matfile.read()\n"
    st += "matfile.close()\n\n"
    st += "# Read the animation data\n"
    st += "animfile = open('%s', 'rb')\n" % os.path.join(alldata_dir, 'ANIMATION.dat').replace('\\', '/')
    st += "animdat = animfile.read()\n"
    st += "animfile.close()\n\n"
    st += "# Get the number of objects\n"
    st += "object_total = unpack('l', animdat[0:4])[0]\n\n"
    st += "# Calculate the number of frames\n"
    st += "frame_total = (len(animdat) - 4) / (((object_total - 1) << 6) + 36)\n\n"
    st += "# Render the animation\n"
    st += "for curframe in range(frame_total):\n\n"
    st += "\tprint 'Rendering frame %d of %d' % (curframe+1, frame_total)\n\n"
    file.write(st)

# function to write animation transform parts
def WriteAnimTransform(file, indent=1, start=1, desc=''):
    # desc: description string
    # start or end of transform?
    if indent:
        idst = '\t'
    else:
        idst = ''
    if start:
        # Single file anim, write transform start program part
        st = "\n" + idst + "#### START " + desc + "\n"
        st += idst + "# Get the animation data\n"
        st += idst + "BMTX = GetAnimData()\n"
        st += idst + "s.transformBegin(transform().setMatrix_rm( BMTX ))\n\n"
    else:
        # end of transform part
        st = idst + "s.transformEnd()\n"
        st += idst + "### END " + desc + "\n\n"
    file.write(st)


######################################################
# FUNCTIONS                                          #
######################################################


def ad_info(lfaces, lv, ch34=0):
    index = 0
    adlist = []
    for i in xrange(len(lv)):
        adlist.append([])
    nfaces = len(lfaces)
    SOLID_FACES = 0
    if ch34:
        # need to check for 3 or 4 verts
        for face in lfaces:
            nv = len(face.v)
            if (nv==3) or (nv==4):
                adlist[face.v[0].index].append(index)
                adlist[face.v[1].index].append(index)
                adlist[face.v[2].index].append(index)
                if nv==4: adlist[face.v[3].index].append(index)
                SOLID_FACES |= (face.smooth==0)
                index += 1
    else:
        for face in lfaces:
            adlist[face.v[0].index].append(index)
            adlist[face.v[1].index].append(index)
            adlist[face.v[2].index].append(index)
            if len(face.v)==4: adlist[face.v[3].index].append(index)
            SOLID_FACES |= (face.smooth==0)
            index += 1
    return adlist, SOLID_FACES


def normalize(vec):
    len = vec[0]*vec[0] + vec[1]*vec[1] + vec[2]*vec[2]
    if len==0.0: return [0.0, 0.0, 0.0]
    len = 1.0/sqrt(len)
    return [vec[0]*len, vec[1]*len, vec[2]*len]


def v_normal(va, vb, vc):
    fv = [0.0, 0.0, 0.0]
    sv = [0.0, 0.0, 0.0]
    fv[0] = vb[0] - va[0]
    fv[1] = vb[1] - va[1]
    fv[2] = vb[2] - va[2]
    sv[0] = vc[0] - va[0]
    sv[1] = vc[1] - va[1]
    sv[2] = vc[2] - va[2]
    normal = [fv[1]*sv[2]-fv[2]*sv[1], fv[2]*sv[0]-fv[0]*sv[2], fv[0]*sv[1]-fv[1]*sv[0]]
    return normalize(normal)


def face_normal(face, vlist):
    vai, vbi, vci = face.v[0].index, face.v[1].index, face.v[2].index
    return v_normal(list(vlist[vai].co), list(vlist[vbi].co), list(vlist[vci].co))


def vangle(va, vb):
    nva = normalize(va)
    nvb = normalize(vb)
    sp = nva[0]*nvb[0] + nva[1]*nvb[1] + nva[2]*nvb[2]
    if sp<0.0: sp = -sp
    return sp


def auto_normal(fnormal, adlist, flist, vlist, cos_angle):
    resul = [0.0, 0.0, 0.0]
    for facei in adlist:
        cnorm = face_normal(flist[facei], vlist)
        if (vangle(fnormal, cnorm) >= cos_angle):
            resul[0] += cnorm[0]
            resul[1] += cnorm[1]
            resul[2] += cnorm[2]
    return normalize(resul)


def FirstFrame():
    return (Blender.Get('curframe')==Blender.Get('staframe'))


def add_lamp(name, savestuff, halocone_list):
    global file
    # possible types:
    # for all:  'Sphere' will enable 1/distance^2 falloff, the most realistic, also default for Lightflow
    #                    when this is not enabled, 1/distance falloff will be used instead, not used with sun or hemi-simulation
    #           'Shadows': will enable or disable of shadow casting for this light
    #           'Negative': will make the light a negative light, it will remove light
    # 'Lamp':
    #   shadowmapped 'soft' light, fake soft shadows
    #       Parameters used: color, energy & distance, Quad1 slider to set the shadow sharpness
    #       shadowmap parameters as well, these are controlled with some external parameters available in the 'more parameters' GUI
    #   when the lamp name has an extension of '_RAY' a pointlight will be created instead, sharp shadows
    #       Parameters used: color, energy & distance
    # 'Spot':
    #   spotlight, shadowmapped 'soft-conic', fake soft shadows
    #       The same parameters as for 'Lamp' (not RAY)
    #       Also use the SpoBl slider to control spot edge sharpness
    #       When 'Halo' is enabled, it will also add a halocone which is actually not part of the light but is faster to render
    #       since the cone has a well defined volume, unlike general volumetric rendering where the volume sampling interval
    #       can be much larger and so takes much more time. On the other hand it can look somewhat better and more realistic.
    #   when the lamp name has an extension of '_RAY' a pointlight will be created instead, sharp shadows
    #       Parameters used: color, energy & distance
    # 'Sun':
    #   sunlight, 'directional', sharp shadows
    #       Parameters used: Color & Energy, distance is irrelevant, so not used
    #       NOTE: when 'shadows' is enabled and fog is used in the scene, lighting doesn't work ???
    # 'Hemi':
    #   not to succesful simulation of Blender's 'Hemi' light, sharp shadows, uses a mix of two light types, 'directional & ambient'
    #       Parameters used: Color & Energy, distance not used
    #       NOTE: when 'shadows' is enabled and fog is used in the scene, lighting doesn't work ???
    #   When 'Square' is enabled, it will create an arealight instead, 'patch', real soft shadows, can be very slow
    #       Parameters used: Color, Energy & Distance
    #       SpoSi slider value divided by 10, controls the size of the arealight

 
    lampObj = Blender.Object.Get(name)
    if lampObj==None: return    # DELETED LAMPS RETURN NONE
    print 'dbg addl lampObj', lampObj

## jms : modif for 228
    if BL_VERSION<=223 :
        lampx = lampObj.data
        # Publisher (BL>223) getType now returns a string, so for compatibility, change <=223 type to string as well
        lpType = ['Lamp', 'Sun', 'Spot', 'Hemi'][lampx.type]
    elif BL_VERSION<228:
        lampx = lampObj.getData()
        lpType = lampx.getType()
    elif BL_VERSION<240:
        lampx = lampObj.getData()
        lpType = ['Lamp', 'Sun', 'Spot', 'Hemi'][lampx.getType()]
    else:
        lampx = lampObj.getData()
        print 'dbg addl lampx', lampx.type
        print dir(lampx)
        lpType = ['Lamp', 'Sun', 'Spot', 'Hemi', 'Area'][lampx.type]
## jms : modif for 228
        #print 'dbg addl', lampx.getType()
        
    
    
    lpMode = lampx.mode


    # SHADOWS? only used with point (_RAY), sun & hemi (area patchlight)
    shadows = (lpMode & 1)


    # MATRIX DIRECTLY AS TRANSFORM, USED FOR PARENTING AND TRACKING
    bmtx = lampObj.matrix

    # ALL LIGHTS PLACED AT ORIGIN, MATRIX TRANSFORMS WILL BE USED TO TRANSLATE AND ROTATE THEM


    # Don't write transform here if this
    # lamp is Hemi+Square Arealight, will be done in WriteAreaLight
    
    if not ((lpType=='Hemi') and ((lpMode & 128)==128)):


        if (Tanimation.val==2):
            desc = "LAMP: " + name
            WriteAnimTransform(file, 1, 1, desc)

        else:
            # If Hemi, not written yet, comments will be written before this
            # completely irrelevant to how it works of course, but I like things to look relatively clean
            TRANS_st = "s.transformBegin(transform().setMatrix_rm(" + BMTX_TO_STRING(bmtx) + "))\n"
            if not ((lpType=='Hemi') & ((lpMode & 128)==0)): file.write(TRANS_st)

    # determine intensity multiply factor, decay parameter
    # completely random formula's (almost...) to come up with something that looks like Blender's result as close as possible
    if (lpMode & 64):


## jms : modif for 228
        if BL_VERSION < 228:
            # SPHERE, does not work well when really far away
            emult = lampx.Energ * lampx.Dist * (lampx.Dist + 1.0) * 0.25
        else:
            emult = lampx.getEnergy() * lampx.getDist() * (lampx.getDist() + 1.0) * 0.25
## jms : modif for 228

        decay = 2.0
    # QUAD light was here, removed, could not make it work
    else:

        # linear fallof otherwise, and again, does not work well when really far away

## jms : modif for 228
        if BL_VERSION < 228:
            emult = lampx.Energ * lampx.Dist
        else:
            emult = lampx.getEnergy() * lampx.getDist()
        decay = 1.0
## jms : modif for 228

    # NEGATIVE?
    if (lpMode & 16): emult *= -1.0

   
    if lpType=='Lamp':

        # check both lamp and object name for 'RAY' extension, if so, create point lightsource


        if name[-3:]=="RAY" or lampx.name[-3:]=="RAY":

            st = anim_indent + "s.lightOn( s.newLight( 'point', [\n"
            # default position (origin), transform is used
            st += "\t\t 'position', vector3(0.0, 0.0, 0.0),\n"
    

## jms : modif for 228
            if BL_VERSION<228: 
                st += "\t\t 'color', vector3(%f, %f, %f),\n" % (lampx.R*emult, lampx.G*emult, lampx.B*emult)
            else:
                st += "\t\t 'color', vector3(%f, %f, %f),\n" % (lampx.col[0]*emult, lampx.col[1]*emult, lampx.col[2]*emult)               
## jms : modif for 228
                
            st += "\t\t 'decay', %f,\n" % decay
            st += "\t\t 'shadows', %d\n" % shadows
            st += "\t ] ) )\n\n"
            file.write(st)
        else:
            
            # 'soft' shadowmapped lightsource
            st = anim_indent + "s.lightOn( s.newLight( 'soft', [\n"
            # default position, transform is used
            st += "\t\t 'position', vector3(0.0, 0.0, 0.0),\n"

## jms : modif for 228
            if BL_VERSION<228: 
                st += "\t\t 'color', vector3(%f, %f, %f),\n" % (lampx.R*emult, lampx.G*emult, lampx.B*emult)
            else:
                st += "\t\t 'color', vector3(%f, %f, %f),\n" % (lampx.col[0]*emult, lampx.col[1]*emult, lampx.col[2]*emult)
## jms : modif for 228

            st += "\t\t 'decay', %f,\n" % decay

## jms : modif for 228
            if BL_VERSION<228: 
                st += "\t\t 'radius', %f,\n" % (0.01 + lampx.Quad1*0.1) # was: 0.03+lampx.SpoBl*0.1
            else:
                st += "\t\t 'radius', %f,\n" % (0.01 + lampx.getQuad1()*0.1)    # was: 0.03+lampx.SpoBl*0.1
## jms : modif for 228

            # Shadowmap parameters from 'more parameters' screen
            st += "\t\t 'zbuffer', %d,\n" % Tsmap_zbuf.val
            st += "\t\t 'samples', %d,\n" % Tsmap_samples.val
            st += "\t\t 'bias', %f" % Tsmap_bias.val

            
            # full path to DATA, replacing backslashes with forward for consistency
            GetOutdir()

            lppath = os.path.join(alldata_dir, ("%s.lamp" % name)).replace('\\', '/')

            if savestuff==3:
                if Tanimation.val==2:
                    # SINGLE ANIMATION SCRIPT, 'action' DETERMINED IN CODE
                    st += ",\n\t\t 'file', '%s, action" % lppath
                else:
                    # render-from-blender animation, only save data when this is the first frame
                    if FirstFrame():
                        st += ",\n\t\t 'file', '%s', 'save'" % lppath
                    else:
                        st += ",\n\t\t 'file', '%s', 'load'" % lppath
            else:
                if savestuff==1:
                    st += ",\n\t\t 'file', '%s', 'save'" % lppath
                elif savestuff==2:
                    st += ",\n\t\t 'file', '%s', 'load'" % lppath
            st += "\n\t ] ) )\n"
            
            
            file.write(st)
            
            
    elif lpType=='Spot':
        

        # LAMP/CONE ANGLE IS HALF BLENDER ANGLE
        if BL_VERSION<228:        
            angle = 0.5*lampx.SpoSi
        else:
            angle = 0.5*lampx.spotSize
            
        if (lpMode & 2):

            # Lamp has "Halo" enabled, save all necessary info
            halocone = []

            halocone.append(name)   # lamp object name

            # Dist is used for Cone height
            if BL_VERSION<228:
               halocone.append(lampx.Dist)
            else:
               halocone.append(lampx.dist)                

            # angle for cone base radius
            halocone.append(angle*pi/180)
            if not Tvolum_toggle.val:

## jms : modif for 228                
                # fake halo
                if BL_VERSION<228:
                    ds = (0.5-0.1*lampx.HaInt)*lampx.Dist*0.016666666
                else:
                    ds = (0.5-0.1*lampx.HaInt)*lampx.getDist()*0.016666666
## jms : modif for 228

            else:

## jms : modif for 228                
                if BL_VERSION<228:
                    # Halo intensity for interior density, use exponential to get a reasonable(?) density estimate
                    ds = 1.0-exp(-lampx.HaInt*0.2)  # HaInt can go up to 5.0
                else:
                    ds = 1.0-exp(-lampx.getHaloIn()*0.2)  # HaInt can go up to 5.0
## jms : modif for 228

            halocone.append(ds)
            # need color for when it is not real volumetric, multiplied by Halo intensity * lamp energy

## jms : modif for 228            
            if BL_VERSION<228:
                em = 0.2 * lampx.HaInt * lampx.Energ
                halocone.append((lampx.R*em, lampx.G*em, lampx.B*em))
            else:
                em = 0.2 * lampx.getHaloInt() * lampx.getEnergy()
                halocone.append((lampx.col[0]*em, lampx.col[0]*em, lampx.col[0]*em))
## jms : modif for 228

            # And finally the matrix
            halocone.append(bmtx)
            halocone_list.append(halocone)
            if Tanimation.val==2:
                # SINGLE FILE ANIM, SAVE CONE TRANSFORM CODE
                hnum = halocone_list.index(halocone)    # use current index as halonumber
                st = "\t### SAVE HALOCONE TRANSFORM\n"
                st += "\tHALO_MTX%d = BMTX\n" % hnum
                file.write(st)

        # check both lamp and object name for 'RAY' extension, if so, create point spotlight
        if name[-3:]=="RAY" or lampx.name[-3:]=="RAY":
            st = anim_indent + "s.lightOn( s.newLight( 'conic', [\n"
            SOFTLT = 0
        else:
            st = anim_indent + "s.lightOn( s.newLight( 'soft-conic', [\n"
            SOFTLT= 1

        # default postion & rotation, matrix is used to transform these
        st += "\t\t 'position', vector3(0.0, 0.0, 0.0),\n"
        st += "\t\t 'direction', vector3(0.0, 0.0, -1.0),\n"

## jms : modif for 228
        if BL_VERSION<228:       
           st += "\t\t 'color', vector3(%f, %f, %f),\n" % (lampx.R*emult, lampx.G*emult, lampx.B*emult)
        else:
           st += "\t\t 'color', vector3(%f, %f, %f),\n" % (lampx.col[0]*emult, lampx.col[1]*emult, lampx.col[2]*emult)            
        if BL_VERSION<=223:
            st += "\t\t 'angle', %f, %f,\n" % ((angle - lampx.SpoBl * angle * 0.5)*pi/180, angle*pi/180)
        elif BL_VERSION<228:
            st += "\t\t 'angle', %f, %f,\n" % ((angle - lampx.spotBlend * angle * 0.5)*pi/180, angle*pi/180)
        else:    
            st += "\t\t 'angle', %f, %f,\n" % ((angle - lampx.getSpotBlend() * angle * 0.5)*pi/180, angle*pi/180)
## jms : modif for 228
            
        st += "\t\t 'decay', %f" % decay

        if SOFTLT:
            
            if BL_VERSION<228:
                st += ",\n\t\t 'radius', %f,\n" % (0.01 + lampx.Quad1*0.1)  # was: 0.03+lampx.SpoBl*0.1
            else:
                st += ",\n\t\t 'radius', %f,\n" % (0.01 + lampx.getQuad1()*0.1)  # was: 0.03+lampx.SpoBl*0.1
                
            
            # Shadowmap parameters from 'more parameters' screen
            st += "\t\t 'zbuffer', %d,\n" % Tsmap_zbuf.val
            st += "\t\t 'samples', %d,\n" % Tsmap_samples.val
            st += "\t\t 'bias', %f" % Tsmap_bias.val
            # check shadowmap save
            # full path to DATA, replacing backslashes with forward for consistency
            GetOutdir()
            lppath = os.path.join(alldata_dir, ("%s.lamp" % name)).replace('\\', '/')
            if savestuff==3:
                if Tanimation.val==2:
                    # SINGLE ANIMATION SCRIPT, 'action' DETERMINED IN CODE
                    st += ",\n\t\t 'file', '%s', action" % lppath
                else:
                    # render-from-blender animation, only save data when this is the first frame
                    if FirstFrame():
                        st += ",\n\t\t 'file', '%s', 'save'" % lppath
                    else:
                        st += ",\n\t\t 'file', '%s', 'load'" % lppath
            else:
                if savestuff==1:
                    st += ",\n\t\t 'file', '%s', 'save'" % lppath
                elif savestuff==2:
                    st += ",\n\t\t 'file', '%s', 'load'" % lppath
        st += "\n\t ] ) )\n"
        file.write(st)

    elif lpType=='Sun':
        # Directional light
        # very strong (no distance attenuation), so only lamp Energy value is used
        st = anim_indent + "s.lightOn( s.newLight( 'directional', [\n"

## jms : modif for 228
        if BL_VERSION<228:              
           st += "\t\t 'color', vector3(%f, %f, %f),\n" % (lampx.R*lampx.Energ, lampx.G*lampx.Energ, lampx.B*lampx.Energ)
        else:
           st += "\t\t 'color', vector3(%f, %f, %f),\n" % (lampx.col[0]*lampx.getEnergy(), lampx.col[1]*lampx.getEnergy(), lampx.col[2]*lampx.getEnergy())
## jms : modif for 228
           
        # default direction, matrix transform is used
        st += "\t\t 'direction', vector3(0.0, 0.0, -1.0),\n"
        st += "\t\t 'shadows', %d\n" % shadows
        st += "\t ] ) )\n"
        file.write(st)

    elif lpType=='Hemi':
        # Not supported in Lightflow, instead creates a directional light combined with an 'ambient' light
        # When 'Square' is set it will automatically create an area light, size is controlled with the SpotSi slider
        if (lpMode & 128):
            # auto arealight
            
## jms : modif for 228
            if BL_VERSION<228:              
                color = (lampx.R*emult, lampx.G*emult, lampx.B*emult)
            else:
                color = (lampx.col[0]*emult, lampx.col[0]*emult, lampx.col[0]*emult)
## jms : modif for 228
                
            # determine size from SpotSi slider
## jms : modif for 228
            if BL_VERSION<228:              
               sz = lampx.SpoSi*0.1    # use 1/10 actual displayed value as size
            else:
               sz = lampx.spotSize*0.1    # use 1/10 actual displayed value as size                
## jms : modif for 228
            
            coords = ((sz, sz, 0.0), (sz, -sz, 0.0), (-sz, -sz, 0.0), (-sz, sz, 0.0))
            # matrix already written here, don't duplicate in WriteAreaLight
            WriteAreaLight(color, bmtx, coords, name, decay, shadows)
        else:
            # directional lamp mixed with an ambient light, distance not used
            st = anim_indent + "### START HEMI SIMULATION\n"
            # Now write transform here
            st += TRANS_st + '\n'
            st += anim_indent + "s.lightOn( s.newLight( 'directional', [\n"

## jms : modif for 228
            if BL_VERSION<228:                          
                st += "\t\t 'color', vector3(%f, %f, %f),\n" % (lampx.R*lampx.Energ, lampx.G*lampx.Energ, lampx.B*lampx.Energ)
            else:
                st += "\t\t 'color', vector3(%f, %f, %f),\n" % (lampx.col[0]*lampx.getEnergy(), lampx.col[1]*lampx.getEnergy(), lampx.col[2]*lampx.getEnergy())
## jms : modif for 228
                
            # default direction, matrix transform is used
            st += "\t\t 'direction', vector3(0.0, 0.0, -1.0),\n"
            st += "\t\t 'shadows', %d\n" % shadows
            st += "\t ] ) )\n"
            # write ambient light
            st += anim_indent + "s.lightOn( s.newLight( 'ambient', [\n"
            # energy must be less than one, so divide by maximum (10)
            
## jms : modif for 228
            if BL_VERSION<228:                          
               emult = sqrt(lampx.Energ * 0.1)
            else:
               emult = sqrt(lampx.getEnergy() * 0.1)                
## jms : modif for 228


## jms : modif for 228
            if BL_VERSION<228:              
                st += "\t\t 'color', vector3(%f, %f, %f),\n" % (lampx.R*emult, lampx.G*emult, lampx.B*emult)
            else:
                st += "\t\t 'color', vector3(%f, %f, %f),\n" % (lampx.col[0]*emult, lampx.col[0]*emult, lampx.col[0]*emult)
## jms : modif for 228
                
            st += "\t ] ) )\n\n"
            # End transform here
            st += "s.transformEnd()\n"
            st += "### END HEMI SIMULATION\n\n"
            file.write(st)

    # transformEnd(), not Hemi+Square Arealight, is done in WriteAreaLight
    if not ((lpType=='Hemi') and ((lpMode & 128)==128)):
        if Tanimation.val==2:
            # SINGLE ANIMATION SCRIPT, END TRANSFORM
            WriteAnimTransform(file, 1, 0, desc)
        elif not ((lpType=='Hemi') & ((lpMode & 128)==0)):
            file.write("s.transformEnd()\n\n")

    # end this block with an extra linebreak
    file.write('\n')


# Arealights from 'PLIGHT' meshes
def add_arealight(name):
    
    blendobject = Blender.Object.Get(name)  # for matrix
    # mesh data from MESH dictionary
    blendmesh = MESH_PT_DICT[name]

    material = None

## jms : modif for 228
    if BL_VERSION>223:
        material = blendmesh.getMaterials()
        if material: material = material[0]
    elif BL_VERSION<228:
        # if material is deleted, material list length will still be nonzero, so check that the name is not None
        if len(blendmesh.mats) and (blendmesh.mats[0]):
            material = Blender.Material.Get(blendmesh.mats[0])
    else:
        # if material is deleted, material list length will still be nonzero, so check that the name is not None
        if len(blendmesh.materials) and (blendmesh.materials[0]):
            material = Blender.Material.Get(blendmesh.materials[0].name)
## jms : modif for 228

    ve = blendmesh.verts
    fc = blendmesh.faces[0]

    if len(fc.v)!=4:
        print "ERROR! use only a 4 point face to export an arealight"
        return

    # all info from matrix
    bmtx = blendobject.matrix

    color = (200.0, 200.0, 200.0)
    decay = 2.0
    if material:
        MATD = GET_MATERIAL_PROPS(material) # 'translate' property names
        energ = MATD['HARD'] * 0.1
        color = (color[0]*MATD['R']*energ, color[1]*MATD['G']*energ, color[2]*MATD['B']*energ)
        # material mode 'shadow' determines if light casts shadows
        shadows = ((MATD['MODE'] & 2)>>1)
    else:
        shadows = 1

    coords = (tuple(fc.v[0].co), tuple(fc.v[1].co), tuple(fc.v[2].co), tuple(fc.v[3].co))

    WriteAreaLight(color, bmtx, coords, name, decay, shadows)


# Used with both PLIGHT mesh and Blender 'Hemi'
def WriteAreaLight(color, mtx, coords, name, decay, shadows):
    # construct patchlight, Lightflow point connection order p1, p2, p4, p3

    if Tanimation.val==2:
        # SINGLE ANIMATION SCRIPT

        desc = "AREALIGHT: " + name
        WriteAnimTransform(file, 1, 1, desc)

        st = "\tp1 = vector3(%f, %f, %f)\n" % coords[0]
        st += "\tp2 = vector3(%f, %f, %f)\n" % coords[1]
        st += "\tp3 = vector3(%f, %f, %f)\n" % coords[3]
        st += "\tp4 = vector3(%f, %f, %f)\n" % coords[2]
        st += "\ts.lightOn( s.newLight( 'patch', [\n"
        st += "\t\t 'color', vector3(%f, %f, %f),\n" % color
        st += "\t\t 'decay', %f,\n" % decay
        st += "\t\t 'shadows', %d,\n" % shadows
        st += "\t\t 'position', p1, p2, p3, p4\n"
        st += "\t ] ))\n"

        file.write(st)

        WriteAnimTransform(file, 1, 0, desc)

    else:

        # for Hemi+Square matrix already written
        st = "s.transformBegin(transform().setMatrix_rm(" + BMTX_TO_STRING(mtx) + "))\n"

        # construct patch, Lightflow connection order p1, p2, p4, p3
        st += "p1 = vector3(%f, %f, %f)\n" % coords[0]
        st += "p2 = vector3(%f, %f, %f)\n" % coords[1]
        st += "p3 = vector3(%f, %f, %f)\n" % coords[3]
        st += "p4 = vector3(%f, %f, %f)\n" % coords[2]

        st += "s.lightOn( s.newLight( 'patch', [\n"
        st += "\t\t 'color', vector3(%f, %f, %f),\n" % color
        st += "\t\t 'decay', %f,\n" % decay
        st += "\t\t 'shadows', %d,\n" % shadows
        st += "\t\t 'position', p1, p2, p3, p4\n"
        st += "\t] ))\n"
    
        if mtx: st += "s.transformEnd()\n\n"

        file.write(st)


# normalize vector inplace, return length
def vnormlen(v):
    vlen = sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
    if vlen!=0.0:
        d = 1.0/vlen
        v[0]*=d;  v[1]*=d;  v[2]*=d
    return vlen


# vector dotproduct
def vdot(v1, v2):
    # dot product
    return v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]


# vector crossproduct
def crossp(v1, v2):
    r = [0.0, 0.0, 0.0]
    r[0] = v1[1]*v2[2] - v1[2]*v2[1]
    r[1] = v1[2]*v2[0] - v1[0]*v2[2]
    r[2] = v1[0]*v2[1] - v1[1]*v2[0]
    return r


# get matrix3x3 determinant 
def determinant3x3(mtx):
    return vdot(mtx[0], crossp(mtx[1], mtx[2]))


# extract euler rotation, scale & position from a single matrix, necessary for parent/child transformations
# does NOT work with non-uniform scaling on parent objects...
# NOT USED ANYMORE EXCEPT FOR THE CAMERA,
# MATRIX DIRECTLY USED INSTEAD (using setMatrix() function in fake lightflowPM module, not actually part of Lightflow)
def infoFromMtx(mat):
    mtx = [list(mat[0][:3]), list(mat[1][:3]), list(mat[2][:3])]
    scale = [0.0, 0.0, 0.0]
    scale[0] = vnormlen(mtx[0])
    scale[1] = vnormlen(mtx[1])
    scale[2] = vnormlen(mtx[2])
    # scaling negative?
    if determinant3x3(mtx)<0.0:
        for i in range(3):
            scale[i] *= -1.0
            mtx[i][0] *= -1.0
            mtx[i][1] *= -1.0
            mtx[i][2] *= -1.0
    angle_y = -asin(max(min(mtx[0][2], 1.0), -1.0))
    C = cos(angle_y)
    if C!=0.0: C = 1.0/C
    angle_x = atan2(mtx[1][2] * C, mtx[2][2] * C)
    angle_z = atan2(mtx[0][1] * C, mtx[0][0] * C)
    return (angle_x, angle_y, angle_z), tuple(scale), tuple(mat[3][:3])


# Convert blender matrix to string
def BMTX_TO_STRING(bmtx):
    st = '\t[[%f, %f, %f, %f],\n' % tuple(bmtx[0])
    st += '\t\t\t\t\t\t [%f, %f, %f, %f],\n' % tuple(bmtx[1])
    st += '\t\t\t\t\t\t [%f, %f, %f, %f],\n' % tuple(bmtx[2])
    st += '\t\t\t\t\t\t [%f, %f, %f, %f]] ' % tuple(bmtx[3])
    return st


# vector * matrix3x3, only needed for blendfile texturespace center calculation
def mulmatvec3x3(v, m):
    r = [0, 0, 0]
    r[0] = v[0]*m[0][0] + v[1]*m[1][0] + v[2]*m[2][0] + m[3][0]
    r[1] = v[0]*m[0][1] + v[1]*m[1][1] + v[2]*m[2][1] + m[3][1]
    r[2] = v[0]*m[0][2] + v[1]*m[1][2] + v[2]*m[2][2] + m[3][2]
    return r


# the big mesh export routine, name = objectname, actual_name = meshname
# duplimesh is flag to indicate this mesh is already written because it is an alt-d linked object
def addmesh(duplimesh, name, actual_name, selectedList, mt_index, real_mt_index, mt_tot):
    global CURRENT_MESH
    global file, meshfile, mesh_hdr_str, mesh_dat_str
    # added: support for more than one material per mesh
    # mt_index = index in used material list, real_mt_index = actual material index as used in mesh

    # CREATE MESH FILE PATHNAME
    # uses actual meshname since possibly duplicated alt-d linked objects can have a different name
    meshpath = os.path.join(alldata_dir, actual_name+".mesh")

    # TEST TO SEE IF THE EXACT FILE ALREADY EXISTS.
    # IF SO, SKIP THE LONG PROCESS OF RE-CALCULATING EVERYTHING
    # UNLESS OTHERWISE SPECIFIED (autocheck)
    if duplimesh:
        # this mesh was already written, so it exists, it is an alt-d linked mesh
        mesh_exists = 1
    elif (Tautocheck.val==1) and os.path.exists(meshpath):
        print  "Meshfile already exists, no need to re-calculate"
        mesh_exists = 1
    elif (Tautocheck.val==2):
        # IF THIS IS A RENDER-FROM-BLENDER-ANIM AND SELECTED EXPORT ONLY, CHECK IF THE MESH IS IN THE LIST
        # UNLESS THIS IS THE FIRST FRAME, IN WHICH CASE IT IS ALWAYS EXPORTED
        if FirstFrame():
            print "First frame, all exported"
            mesh_exists = 0
        else:
            if name in selectedList:
                # MESH IS SELECTED FOR EXPORT, FORCE RECALCULATION
                print "%s recalculated" % name
                mesh_exists = 0
            else:
                # NOT IN THE LIST, ONLY EXPORT IF IT DOESN'T EXIST YET
                mesh_exists = os.path.exists(meshpath)
                if mesh_exists:
                    print "Mesh exists, transform only export"
                else:
                    print "Mesh does not exist, need to fully export"
    else: mesh_exists = 0

    numfaces = 0
    numvertlist = []
    facepointlist = []

    # Smooth normal calculations?
    if (name[-5:-2]=="_AS"):
        cos_angle = cos(float(name[-2:]) * pi / 180.0)
        if cos_angle==1.0:
            print "Autosmooth 0, face normals will be used"
        else:
            print "Applying autosmooth %s" % name[-2:]
    else:
        # Code after this will check if any face has smooth set to 0, in which case normal calculations will be forced anyway
        cos_angle = None

    # Flag for solid shading when enabled
    SOLID_FACES = 0

    if not mesh_exists:
        # more than one material? only get the mesh once, untill all materials have been processed
        # This helps a bit (but NOT eliminates) to lessen the memory usage of GetRaw, as it makes a complete copy of the mesh
        # without releasing it unless quiting Blender
        # THIS IS A MAJOR STUMBLING BLOCK FOR ANIMATION
        if mt_tot>1 and mt_index==0:
            CURRENT_MESH = Blender.NMesh.GetRawFromObject(name)
        elif mt_tot<=1:
            CURRENT_MESH = Blender.NMesh.GetRawFromObject(name)

        

        ## Lets add points and tex coords and normals and.....
        textlist = []
        facetextlist = []

        # corrected: now only accepts 3 or 4 vert polys, ignoring all others, previous code would assume quad when len(verts)!=3

        # Only the faces which correspond to the current material index are exported

        if mt_tot>1:
            ################# MATERIAL SEPARATION ######################
            # Complicated bit, for efficiency, need to only export those faces which have
            # the specified material, but faces can share vertices, so this code below
            # is to take care of this, which in essence creates a new mesh
            # without adding extra faces or vertices, except of course for the edge faces at the material borders

            # list of new vertex coordinates
            blendmeshverts = []
            # list of new faces
            blendmeshfaces = []
            # dictionary of all shared vertex indices for all faces
            vtx_idx_map = {}
            # dictionary which holds all the old vertex indices belonging to this face
            face_vtx_idx = {}

            # sift out all vertices and faces which have
            # the specified material index
            fn = 0
            # progress bar draw counters, only draw once every 512 'items'
            # just drawing the progress bar everytime can slow down things enormously
            pinc = 1.0/len(CURRENT_MESH.faces)
            pcount = 0.0
            ipinc = 0
            for face in CURRENT_MESH.faces:
                if ((ipinc & 511)==0): pbar(pcount, 'Face material check...')
                ipinc += 1
                pcount += pinc
                # from bug report by S68: invalid faces were not 'catched' early enough,
                # causing an 'index list out of range' error when used with AutoSmooth
                nv = len(face.v)
                if (face.mat==real_mt_index) and ((nv==3) or (nv==4)):
                    for v in face.v:
                        vtx_idx_map[v.index] = 0
                    face_vtx_idx[fn] = face
                    fn += 1

            # Make the new vertex list,
            # and map all old indices in the vertex index dictionary
            # to the new indices, which is just 0 to len(list)-1
            new_idx = 0
            for k in vtx_idx_map.keys():
                blendmeshverts.append(CURRENT_MESH.verts[k])
                vtx_idx_map[k] = new_idx
                new_idx += 1

            # progress bar draw counters, only draw once every 512 'items'
            nflen = len(face_vtx_idx.keys())
            if nflen: pinc = 1.0/nflen
            pcount = 0.0
            ipinc = 0

            # Create new faces using the vertex index mapping dictionary
            # This uses an actual NMesh.Face(), so code below can be run without changes
            for fn in face_vtx_idx.keys():
                if ((ipinc & 511)==0): pbar(pcount, 'Face material reconstruct...')
                ipinc += 1
                pcount += pinc
                old_face = face_vtx_idx[fn]
                new_face = Blender.NMesh.Face()
                # copy all data, but replace the vertex list
                for v in face_vtx_idx[fn].v:
                    new_face.v.append(CURRENT_MESH.verts[vtx_idx_map[v.index]])
                # copy remaining data, not actual copies (not necessary, 'pointers' good enough here)
                new_face.uv = old_face.uv
                new_face.mat = real_mt_index
                new_face.smooth = old_face.smooth
                SOLID_FACES |= (new_face.smooth==0) # force normal calculation?
                blendmeshfaces.append(new_face)

            ############################################################

        # if less than one or no materials, use actual mesh vertex and face list
        # in case of autosmooth, also initialize here
        if mt_tot>1:
            # more than one material, use the separated data calculated above
            bfaces = blendmeshfaces
            bverts = blendmeshverts
            # really stupid mistake here, discovered by 'Skates'
            # ad_info returns two variables, but only one is used here, which produced a 'tuple index out of range' error
            if cos_angle <= 1.0: adlist = ad_info(bfaces, bverts)[0]    # 3/4 vert check already done, no need to do again
        else:
            # one or no material, use actual mesh data
            bfaces = CURRENT_MESH.faces
            bverts = CURRENT_MESH.verts
            # need to at least check for solid faces, so run this independent if cos_angle<=1 or not
            adlist, SOLID_FACES = ad_info(bfaces, bverts, 1)    # 3/4 vert & solid check not done yet, do in ad_info

        if SOLID_FACES:
            print "Mesh contains faces with solid shading, will force normal calculations"

        # All lists that are used to write data, are now single element lists,
        # meaning they don't contain lists themselves.
        # This is so that they can be converted to tuples and used as an argument
        # to apply() for faster data packing and writing.

        i = 0
        if CURRENT_MESH.hasFaceUV():
            print "Exporting uv"
            # progress bar draw counters, only draw once every 512 'items'
            pinc = 1.0/len(bfaces)
            pcount = 0.0
            ipinc = 0
            for bface in bfaces:
                if ((ipinc & 511)==0): pbar(pcount, 'UV coordinates...')
                ipinc += 1
                pcount += pinc
                if (bface.mat==real_mt_index) or (mt_tot==-1):
                    nfaces = len(bface.v)
                    if nfaces==3:
                        textlist.append(bface.uv[0][0]);  textlist.append(1.0 - bface.uv[0][1])
                        textlist.append(bface.uv[1][0]);  textlist.append(1.0 - bface.uv[1][1])
                        textlist.append(bface.uv[2][0]);  textlist.append(1.0 - bface.uv[2][1])
                        facetextlist.append(i)
                        facetextlist.append(i+1)
                        facetextlist.append(i+2)
                        i += 3
                    elif nfaces==4:
                        textlist.append(bface.uv[0][0]);  textlist.append(1.0 - bface.uv[0][1])
                        textlist.append(bface.uv[1][0]);  textlist.append(1.0 - bface.uv[1][1])
                        textlist.append(bface.uv[2][0]);  textlist.append(1.0 - bface.uv[2][1])
                        textlist.append(bface.uv[3][0]);  textlist.append(1.0 - bface.uv[3][1])
                        facetextlist.append(i)
                        facetextlist.append(i+1)
                        facetextlist.append(i+2)
                        facetextlist.append(i+3)
                        i += 4
        else :
            textlist.append(0.0);  textlist.append(0.0)
            for bface in bfaces:
                nfaces = len(bface.v)
                if nfaces==3:
                    facetextlist.append(0)
                    facetextlist.append(0)
                    facetextlist.append(0)
                elif nfaces==4:
                    facetextlist.append(0)
                    facetextlist.append(0)
                    facetextlist.append(0)
                    facetextlist.append(0)

        facenormallist = []
        faceindexnormal = []
        normalindex = []
        fnindex = 0
        # progress bar draw counters, only draw once every 512 'items'
        pinc = 1.0/len(bfaces)
        pcount = 0.0
        ipinc = 0
        for blendface in bfaces:
            if ((ipinc & 511)==0): pbar(pcount, 'Mesh Faces...')
            ipinc += 1
            pcount += pinc
            if (blendface.mat==real_mt_index) or (mt_tot==-1):
                nfaces = len(blendface.v)
                if nfaces==3:
                    numvertlist.append(3)
                    facepointlist.append(blendface.v[0].index)
                    facepointlist.append(blendface.v[1].index)
                    facepointlist.append(blendface.v[2].index)
                    # Autosmooth calculation
                    if (cos_angle<=1.0) or SOLID_FACES:
                        normal = face_normal(blendface, bverts)
                        if (cos_angle==1.0) or (not blendface.smooth):
                            # If angle==1.0 or face shading solid, normal == face normal, no need to calculate normals.
                            # Need to append normal several times, can't just use the index several times with a single normal,
                            # since smooth and solid shading can be mixed
                            facenormallist.append(normal[0]);  facenormallist.append(normal[1]);  facenormallist.append(normal[2])
                            facenormallist.append(normal[0]);  facenormallist.append(normal[1]);  facenormallist.append(normal[2])
                            facenormallist.append(normal[0]);  facenormallist.append(normal[1]);  facenormallist.append(normal[2])
                            normalindex.append(fnindex)
                            normalindex.append(fnindex+1)
                            normalindex.append(fnindex+2)
                            fnindex += 3
                        elif (cos_angle==None) and blendface.smooth:
                            # normal shading, use vertex normals directly from mesh
                            facenormallist.append(blendface.v[0].no[0]);  facenormallist.append(blendface.v[0].no[1]);  facenormallist.append(blendface.v[0].no[2])
                            normalindex.append(fnindex)
                            facenormallist.append(blendface.v[1].no[0]);  facenormallist.append(blendface.v[1].no[1]);  facenormallist.append(blendface.v[1].no[2])
                            normalindex.append(fnindex+1)
                            facenormallist.append(blendface.v[2].no[0]);  facenormallist.append(blendface.v[2].no[1]);  facenormallist.append(blendface.v[2].no[2])
                            normalindex.append(fnindex+2)
                            fnindex += 3
                        else:
                            # calculate autosmooth normals
                            snorm = auto_normal(normal, adlist[blendface.v[0].index], bfaces, bverts, cos_angle)
                            facenormallist.append(snorm[0]);  facenormallist.append(snorm[1]);  facenormallist.append(snorm[2])
                            snorm = auto_normal(normal, adlist[blendface.v[1].index], bfaces, bverts, cos_angle)
                            facenormallist.append(snorm[0]);  facenormallist.append(snorm[1]);  facenormallist.append(snorm[2])
                            snorm = auto_normal(normal, adlist[blendface.v[2].index], bfaces, bverts, cos_angle)
                            facenormallist.append(snorm[0]);  facenormallist.append(snorm[1]);  facenormallist.append(snorm[2])
                            normalindex.append(fnindex)
                            normalindex.append(fnindex+1)
                            normalindex.append(fnindex+2)
                            fnindex += 3
                    numfaces += 1
                elif nfaces==4:
                    numvertlist.append(4)
                    facepointlist.append(blendface.v[0].index)
                    facepointlist.append(blendface.v[1].index)
                    facepointlist.append(blendface.v[2].index)
                    facepointlist.append(blendface.v[3].index)
                    # Autosmooth calculation
                    if (cos_angle<=1.0) or SOLID_FACES:
                        normal = face_normal(blendface, bverts)
                        if (cos_angle==1.0) or (not blendface.smooth):
                            # if angle==1.0 or face shading solid, normal == face normal, no need to calculate normals
                            # Need to append normal several times, can't just use the index several times with a single normal,
                            # since smooth and solid shading can be mixed
                            facenormallist.append(normal[0]);  facenormallist.append(normal[1]);  facenormallist.append(normal[2])
                            facenormallist.append(normal[0]);  facenormallist.append(normal[1]);  facenormallist.append(normal[2])
                            facenormallist.append(normal[0]);  facenormallist.append(normal[1]);  facenormallist.append(normal[2])
                            facenormallist.append(normal[0]);  facenormallist.append(normal[1]);  facenormallist.append(normal[2])
                            normalindex.append(fnindex)
                            normalindex.append(fnindex+1)
                            normalindex.append(fnindex+2)
                            normalindex.append(fnindex+3)
                            fnindex += 4
                        elif (cos_angle==None) and blendface.smooth:
                            # normal shading, use vertex normals directly from mesh
                            facenormallist.append(blendface.v[0].no[0]);  facenormallist.append(blendface.v[0].no[1]);  facenormallist.append(blendface.v[0].no[2])
                            normalindex.append(fnindex)
                            facenormallist.append(blendface.v[1].no[0]);  facenormallist.append(blendface.v[1].no[1]);  facenormallist.append(blendface.v[1].no[2])
                            normalindex.append(fnindex+1)
                            facenormallist.append(blendface.v[2].no[0]);  facenormallist.append(blendface.v[2].no[1]);  facenormallist.append(blendface.v[2].no[2])
                            normalindex.append(fnindex+2)
                            facenormallist.append(blendface.v[3].no[0]);  facenormallist.append(blendface.v[3].no[1]);  facenormallist.append(blendface.v[3].no[2])
                            normalindex.append(fnindex+3)
                            fnindex += 4
                        else:
                            snorm = auto_normal(normal, adlist[blendface.v[0].index], bfaces, bverts, cos_angle)
                            facenormallist.append(snorm[0]);  facenormallist.append(snorm[1]);  facenormallist.append(snorm[2])
                            snorm = auto_normal(normal, adlist[blendface.v[1].index], bfaces, bverts, cos_angle)
                            facenormallist.append(snorm[0]);  facenormallist.append(snorm[1]);  facenormallist.append(snorm[2])
                            snorm = auto_normal(normal, adlist[blendface.v[2].index], bfaces, bverts, cos_angle)
                            facenormallist.append(snorm[0]);  facenormallist.append(snorm[1]);  facenormallist.append(snorm[2])
                            snorm = auto_normal(normal, adlist[blendface.v[3].index], bfaces, bverts, cos_angle)
                            facenormallist.append(snorm[0]);  facenormallist.append(snorm[1]);  facenormallist.append(snorm[2])
                            normalindex.append(fnindex)
                            normalindex.append(fnindex+1)
                            normalindex.append(fnindex+2)
                            normalindex.append(fnindex+3)
                            fnindex += 4
                    numfaces += 1

        # WRITE THE BINARY MESH DATA

        # INDIVIDUAL MESH HEADERS
        # initialize the data strings
        if (mt_tot>1) and (mt_index==0):
            # more than one material, first material
            mesh_dat_str = ''
            # number of meshes, as many meshes in the file as the total of materials the mesh uses
            mesh_hdr_str = pack("l", mt_tot)
        elif mt_tot<=1:
            # single or no material
            mesh_dat_str = ''
            # number of meshes, single mesh in the file
            mesh_hdr_str = pack("l", 1)

        # number of verts
        mesh_hdr_str += pack("l", len(bverts))
        # number of norms
        if (cos_angle<=1.0) or SOLID_FACES:
            # calculated smooth normals
            if PRINT_TRACE: print "number of normals %d" % (len(facenormallist)/3)
            mesh_hdr_str += pack("l", (len(facenormallist)/3))
        else:
            # list of normals from actual faces
            blendmeshnormals = []
            for v in bverts:
                blendmeshnormals.append(v.no[0])
                blendmeshnormals.append(v.no[1])
                blendmeshnormals.append(v.no[2])
            if PRINT_TRACE: print "number of normals %d" % (len(blendmeshnormals)/3)
            mesh_hdr_str += pack("l", (len(blendmeshnormals)/3))

        # number of texcoords
        if PRINT_TRACE: print "number of texcoords %d" % (len(textlist)/2)
        mesh_hdr_str += pack("l", (len(textlist)/2))
        # number of faces
        if PRINT_TRACE: print "number of faces %d" % numfaces
        mesh_hdr_str += pack("l", numfaces)

        # total number of verts
        totv = 0
        for i in numvertlist: totv += i
        if PRINT_TRACE: print "number of total vertices %d" % totv
        mesh_hdr_str += pack("l", totv)

        # MESH ACTUAL DATA
        # vertices
        if PRINT_TRACE: print "number of vertices %d" % len(bverts)
        vco = []
        for v in bverts:
            vco.append(v.co[0])
            vco.append(v.co[1])
            vco.append(v.co[2])
        pack_str = "%df" % len(vco)
        vco.insert(0, pack_str)
        mesh_dat_str += apply(pack, tuple(vco))

        # normals
        if (cos_angle<=1.0) or SOLID_FACES:
            # calculated smooth normals
            pack_str = "%df" % len(facenormallist)
            facenormallist.insert(0, pack_str)
            mesh_dat_str += apply(pack, tuple(facenormallist))
        else:
            # direct copy of mesh normals
            pack_str = "%df" % len(blendmeshnormals)
            blendmeshnormals.insert(0, pack_str)
            mesh_dat_str += apply(pack, tuple(blendmeshnormals))

        # texcoords
        pack_str = "%df" % len(textlist)
        textlist.insert(0, pack_str)
        mesh_dat_str += apply(pack, tuple(textlist))

        # num. of verts per face list
        pack_str = "%dl" % len(numvertlist)
        numvertlist.insert(0, pack_str)
        mesh_dat_str += apply(pack, tuple(numvertlist))

        # vertex index list
        pack_str = "%dl" % len(facepointlist)
        facepointlist.insert(0, pack_str)
        # might be written twice, below in normal index, so make tuple here
        facepointlist = tuple(facepointlist)
        mesh_dat_str += apply(pack, facepointlist)

        # normal index list
        if (cos_angle<=1.0) or SOLID_FACES:
            pack_str = "%dl" % len(normalindex)
            normalindex.insert(0, pack_str)
            mesh_dat_str += apply(pack, tuple(normalindex))
        else:
            # facepointlist already contains pack_str above
            mesh_dat_str += apply(pack, facepointlist)

        # texcoord index list
        pack_str = "%dl" % len(facetextlist)
        facetextlist.insert(0, pack_str)
        mesh_dat_str += apply(pack, tuple(facetextlist))

        if PRINT_TRACE: print "header, data: ", len(mesh_hdr_str), len(mesh_dat_str)
        # finally write the total mesh data when done
        if (mt_tot>1) and (mt_index==(mt_tot-1)):
            # more than one material, last material
            meshfile = open(meshpath, 'wb')
            meshfile.write(mesh_hdr_str)
            meshfile.write(mesh_dat_str)
            meshfile.close()
            if PRINT_TRACE: print "Mesh file saved to: %s " % meshpath
            del CURRENT_MESH, mesh_dat_str, mesh_hdr_str
            CURRENT_MESH = None
        elif mt_tot<=1:
            meshfile = open(meshpath, 'wb')
            meshfile.write(mesh_hdr_str)
            meshfile.write(mesh_dat_str)
            meshfile.close()
            if PRINT_TRACE: print "Mesh file saved to: %s " % meshpath
            del CURRENT_MESH, mesh_dat_str, mesh_hdr_str
            CURRENT_MESH = None

        # END PACKED MESH WRITE

    if mt_tot>1:
        mt_idx = mt_index
    else:
        mt_idx = 0
    # better use full path to mesh, replace any '\' with '/'
    meshpath = meshpath.replace('\\', '/')
    if name[-5:]!="_SURF":
        file.write(anim_indent + "s.addObject( s.newObject( 'mesh', [ 'file', '%s', %d] ) )\n" % (meshpath, mt_idx))


#########################################
# CUSTOM MATERIALS
# USES SOME OF BLENDER'S MATERIAL PARAMETERS WHICH CAN'T BE USED IN LIGHTFLOW FOR OTHER PURPOSES

def STRING_CORRECT(st):
    # replace all disallowed chars in variable names (materials)
    # must be possible to do shorter (intersect possible?)
    # all?
    nst = st.replace(' ', '_').replace('.', '_')
    nst = nst.replace('-', '_').replace('+', '_')
    nst = nst.replace('(', '_').replace(')', '_')
    nst = nst.replace('*', '_').replace('&', '_')
    nst = nst.replace('^', '_').replace('%', '_')
    nst = nst.replace('$', '_').replace('#', '_')
    nst = nst.replace('@', '_').replace('!', '_')
    nst = nst.replace('~', '_').replace('`', '_')
    nst = nst.replace('{', '_').replace('}', '_')
    nst = nst.replace('[', '_').replace(']', '_')
    nst = nst.replace(';', '_').replace(':', '_')
    nst = nst.replace("'", '_').replace('"', '_')
    nst = nst.replace(',', '_').replace('.', '_')
    nst = nst.replace('<', '_').replace('>', '_')
    nst = nst.replace('/', '_').replace('?', '_')
    return nst

# FUNCTION TO TRANSLATE DIFFERENT MATERIAL PROPERTY NAMES IN DIFFERENT VERSIONS
# returns dictionary
def GET_MATERIAL_PROPS(mt):
    matdict = {}
    st = "matdict['ALPHA'] = mt." + MSP_BL_VARS['BLEND_ALPHA'] + "\n"
    st += "matdict['AMB'] = mt." + MSP_BL_VARS['BLEND_AMB'] + "\n"
    st += "matdict['R'] = mt." + MSP_BL_VARS['BLEND_COLOR_R'] + "\n"
    st += "matdict['G'] = mt." + MSP_BL_VARS['BLEND_COLOR_G'] + "\n"
    st += "matdict['B'] = mt." + MSP_BL_VARS['BLEND_COLOR_B'] + "\n"
    st += "matdict['EMIT'] = mt." + MSP_BL_VARS['BLEND_EMIT'] + "\n"
    st += "matdict['HARD'] = mt." + MSP_BL_VARS['BLEND_HARD'] + "\n"
    st += "matdict['MIRR'] = mt." + MSP_BL_VARS['BLEND_COLOR_MIR_R'] + "\n"
    st += "matdict['MIRG'] = mt." + MSP_BL_VARS['BLEND_COLOR_MIR_G'] + "\n"
    st += "matdict['MIRB'] = mt." + MSP_BL_VARS['BLEND_COLOR_MIR_B'] + "\n"
    st += "matdict['SPECR'] = mt." + MSP_BL_VARS['BLEND_COLOR_SPEC_R'] + "\n"
    st += "matdict['SPECG'] = mt." + MSP_BL_VARS['BLEND_COLOR_SPEC_G'] + "\n"
    st += "matdict['SPECB'] = mt." + MSP_BL_VARS['BLEND_COLOR_SPEC_B'] + "\n"
    st += "matdict['REF'] = mt." + MSP_BL_VARS['BLEND_REF'] + "\n"
    st += "matdict['SPTRA'] = mt." + MSP_BL_VARS['BLEND_SPTRA'] + "\n"
    st += "matdict['SPEC'] = mt." + MSP_BL_VARS['BLEND_SPEC'] + "\n"
    st += "matdict['MODE'] = mt." + MSP_BL_VARS['BLEND_MATMODE'] + "\n"
    exec(st)
    return matdict


# for all material routines, check duplication of material and/or pattern
def checkMtTx(matname, texname, matnum):
    global texnames, matnames
    if matname==None:   # ONLY HAPPENS FOR WORLD_LIGHT
        matname = 'WORLD_LIGHT'
    else:
        matname = STRING_CORRECT(matname)   # correct output name
    # is this material already written? if so, leave now, no duplication of materials
    if matname in matnames:
        print "%s already written, not duplicated" % matname
        return None, None
    # no, it isn't, save the name
    matnames.append(matname)
    if texname:
        PN = texname.replace('\\', '/') # forward slashes in paths compatible with both platforms
        # was this texture already used?
        if texname not in texnames.keys():
            patname = "LFPAT%d" % matnum
            if matname=='WORLD_LIGHT':      # sphere mapped texture for WORLD_LIGHT
                matfile.write("%s = s.newPattern( 'map', [ 'texture', s.newTexture('%s'), 'type', 'sphere'] )\n" % (patname, PN))
            else:
                matfile.write("%s = s.newPattern( 'map', [ 'texture', s.newTexture('%s'), 'type', 'surface'] )\n" % (patname, PN))
            texnames[texname] = patname
        else:
            patname = texnames[texname]
    else:
        patname = None
    return matname, patname


# FOR RADIOSITY AND CAUSTICS: ONLY WRITE THE CORRESPONDING MATERIAL PARAMETERS, WHEN THESE ARE ACTUALLY ENABLED
# OTHERWISE (AT LEAST ON MY SYSTEM) LIGHTFLOW WILL CRASH ON EXIT

# radiosity can switched on and off with buttons in 'more parameters' screen
def WRITE_GLASS(material, texname, matnum, colrm, dispm, radiosity, caustics):
    # Ref * 2.5 is used to set the refraction index
    # RGB color is used to set transmission and specular transmission amount
    # mirror color is used to set the reflection color and amount
    # specular color is used to set the specular reflection color
    # Spec slider is used to set specular amount
    # SpTra slider is used to set specular shinyness
    # Hard slider is used to set specular roughness
    # Emit*0.01 is used to set the amount of refraction/reflection blur
    # if uv-texture is used, mirror, specular, transmission and specular transmission are modulated by it,
    # also possibly used as displacement map
    # If caustics is not enabled, fake caustics are used instead
    matname, patname = checkMtTx(material.name, texname, matnum)
    if (matname==None) and (patname==None): return  # material/pattern already written
    MATD = GET_MATERIAL_PROPS(material) # 'translate' property names
    st = "%s = s.newMaterial( 'generic', [\n" % matname
    st += "\t\t 'fresnel', 1,\n"
    st += "\t\t 'IOR', %f,\n" % (MATD['REF'] * 2.5)
    # no diffuse reflection or transmission
    st += "\t\t 'kdr', vector3(0.0, 0.0, 0.0),\n"
    st += "\t\t 'kdt', vector3(0.0, 0.0, 0.0),\n"
    # specular reflection
    st += "\t\t 'ksr', vector3(%f, %f, %f),\n" % (MATD['SPECR']*MATD['SPEC'], MATD['SPECG']*MATD['SPEC'], MATD['SPECB']*MATD['SPEC'])
    if colrm and patname: st += "\t\t 'ksr', %s,\n" % patname
    # specular transmission
    st += "\t\t 'kst', vector3(%f, %f, %f),\n" % (MATD['R']*MATD['SPEC'], MATD['G']*MATD['SPEC'], MATD['B']*MATD['SPEC'])
    if colrm and patname: st += "\t\t 'kst', %s,\n" % patname
    # reflection
    st += "\t\t 'kr', vector3(%f, %f, %f),\n" % (MATD['MIRR'], MATD['MIRG'], MATD['MIRB'])
    if colrm and patname: st += "\t\t 'kr', %s,\n" % patname
    # transmission
    st += "\t\t 'kt', vector3(%f, %f, %f),\n" % (MATD['R'], MATD['G'], MATD['B'])
    if colrm and patname: st += "\t\t 'kt', %s,\n" % patname
    # displacement mapping
    if dispm and patname: st += "\t\t 'displacement', %s,\n" % patname
    # ksg removed, only km is really needed, can be set higher than in standard material, seems more appropriate here
    st += "\t\t 'km', %f,\n" % (1.0 / MATD['HARD'])
    # shinyness enhancement
    st += "\t\t 'shinyness', %f,\n" % MATD['SPTRA']
    # refraction/reflection blur, only sets amount of blur.
    # Since generally very small values will be used, the range is restricted to 0.0 -  0.01
    st += "\t\t 'kb', %f, %d,\n" % (MATD['EMIT'] * 0.01, Trblur_samples.val)
    if Tglit_toggle.val: st += "\t\t 'glitter', 1,\n"
    if caustics:
        st += "\t\t 'transmission', 0,\n"
        # LIGHTFLOW WILL CRASH IF USED INSIDE THE MATERIAL AND RADIOSITY IS DISABLED
        if radiosity: st += "\t\t 'radiosity', %d,\n" % Trad_glas.val
        st += "\t\t 'caustics', 2, 2\n"
    else:
        if radiosity: st += "\t\t 'radiosity', %d,\n" % Trad_glas.val
        st += "\t\t 'transmission', 1\n"
    st += "\t ] )\n\n"
    matfile.write(st)


# suggested by S68, enabled radiosity in material, but now can be switched on and off with buttons in 'more parameters' screen
def WRITE_METAL(material, texname, matnum, colrm, dispm, radiosity, caustics):
    # material Ref*25+1.0 is used to set the refraction index (yes, metal has a refraction index!)
    # RGB color is used to set base diffuse color
    # mirror color is used to set the reflection color and amount
    # specular color is used to set the specular reflection color
    # Spec slider is used to set specular amount
    # SpTra slider is used to set specular shinyness
    # Hard slider is used to set specular roughness
    # Emit*0.01 is used to set the amount of refraction/reflection blur
    # if uv-texture is used, mirror, specular, transmission and specular transmission are modulated by it,
    # also possibly used as displacement map
    matname, patname = checkMtTx(material.name, texname, matnum)
    if (matname==None) and (patname==None): return  # material/pattern already written
    MATD = GET_MATERIAL_PROPS(material) # 'translate' property names
    st = "%s = s.newMaterial( 'generic', [\n" % matname
    st += "\t\t 'fresnel', 1,\n"
    st += "\t\t 'IOR', %f,\n" % (1.0 + MATD['REF']*25.0)
    # diffuse base colour
    st += "\t\t 'kdr', vector3(%f, %f, %f),\n" % (MATD['R'], MATD['G'], MATD['B'])
    if colrm and patname: st += "\t\t 'kdr', %s,\n" % patname
    # specular reflection
    st += "\t\t 'ksr', vector3(%f, %f, %f),\n" % (MATD['SPECR']*MATD['SPEC'], MATD['SPECG']*MATD['SPEC'], MATD['SPECB']*MATD['SPEC'])
    if colrm and patname: st += "\t\t 'ksr', %s,\n" % patname
    # reflection
    st += "\t\t 'kr', vector3(%f, %f, %f),\n" % (MATD['MIRR'], MATD['MIRG'], MATD['MIRB'])
    if colrm and patname: st += "\t\t 'kr', %s,\n" % patname
    # displacement mapping
    if dispm and patname: st += "\t\t 'displacement', %s,\n" % patname
    # ksg removed, only km is really needed, can be set higher than in standard material, seems more appropriate here
    st += "\t\t 'km', %f,\n" % (1.0 / MATD['HARD'])
    # shinyness enhancement
    st += "\t\t 'shinyness', %f,\n" % MATD['SPTRA']
    # refraction/reflection blur, only sets amount of blur.
    # Since generally very small values will be used, the range is restricted to 0.0 -  0.01
    st += "\t\t 'kb', %f, %d,\n" % (MATD['EMIT'] * 0.01, Trblur_samples.val)
    if Tglit_toggle.val: st += "\t\t 'glitter', 1,\n"
    if radiosity: st += "\t\t 'radiosity', %d,\n" % Trad_metl.val
    if caustics: st += "\t\t 'caustics', 1, 1\n"
    st += "\t ] )\n\n"
    matfile.write(st)


def WRITE_STANDARD(material, texname, matnum, colrm, dispm, radiosity, caustics):
    global texnames, matnames
    # RGB color sliders are used to set diffuse color
    # Specular color sliders are used to set specular color
    # Spec slider is used to set amount of specularity
    # material Hard is used to set the specular 'roughness'
    # SpTra slider is used to enhance specular shinyness
    # Ref slider is is used to set the amount of diffuse color
    # Emit slider is used to set ambient color
    # Alpha slider is used to simulate Blender's alpha behaviour when 'ZTransp' is set
    # When 'traceable' is not enabled, the material won't cast shadows
    # if a texture is given, it will be used to modulate diffuse, specular and emit value, also as displacement if specified
    matname, patname = checkMtTx(material.name, texname, matnum)
    if (matname==None) and (patname==None): return  # material/pattern already written
    MATD = GET_MATERIAL_PROPS(material) # 'translate' property names
    st = "%s = s.newMaterial( 'generic', [\n" % matname
    if (MATD['MODE'] & 64):
        # ZTransp enabled, use alpha value to calculate colour
        # since default IOR is set to 1.0, this will look similar to the Blender result
        t = 1.0 - MATD['ALPHA']
        st += "\t\t 'kt', vector3(%f, %f, %f),\n" % (t, t, t)
        t = MATD['ALPHA'] * MATD['REF']
        st += "\t\t 'kdr', vector3(%f, %f, %f),\n" % (MATD['R']*t, MATD['G']*t, MATD['B']*t)
    else:
        # normal mode, color is diffuse color
        st += "\t\t 'kdr', vector3(%f, %f, %f),\n" % (MATD['R']*MATD['REF'], MATD['G']*MATD['REF'], MATD['B']*MATD['REF'])
    if colrm and patname: st += "\t\t 'kdr', %s,\n" % patname
    # emit value is used to calculate ambient color
    st += "\t\t 'ka', vector3(%f, %f, %f),\n" % (MATD['R']*MATD['EMIT'], MATD['G']*MATD['EMIT'], MATD['B']*MATD['EMIT'])
    # SpTra value to enhance specular shinyness
    st += "\t\t 'shinyness', %f,\n" % MATD['SPTRA']
    if colrm and patname: st += "\t\t 'ka', %s,\n" % patname
    # displacement
    if dispm and patname: st += "\t\t 'displacement', %s,\n" % patname
    # specular color/amount
    st += "\t\t 'ksr', vector3(%f, %f, %f),\n" % (MATD['SPECR']*MATD['SPEC'], MATD['SPECG']*MATD['SPEC'], MATD['SPECB']*MATD['SPEC'])
    if colrm and patname: st += "\t\t 'ksr', %s,\n" % patname
    # specular roughness, ksg is left at it's default, whatever it is, looks closer to Blender settings
    st += "\t\t 'km', %f" % (MATD['HARD'] ** -0.7071068)
    if Tglit_toggle.val: st += ",\n\t\t 'glitter', 1"
    if radiosity: st += ",\n\t\t 'radiosity', 1"
    # switch on transmission if ZTransp enabled
    if (MATD['MODE'] & 64) and not caustics: st += ",\n\t\t 'transmission', 1"
    # disable shadows when 'traceable' siwtched off
    if ((MATD['MODE'] & 1)==0): st += ",\n\t\t 'shadowing', 0.0"
    st += "\n\t ] )\n\n"
    matfile.write(st)


def WRITE_AMBIENT(material, texname, matnum, WORLD_COLOR):
    # material might be None when used for WORLD_LIGHT
    if material:
        matname, patname = checkMtTx(material.name, texname, matnum)
    else:
        matname, patname = checkMtTx(None, texname, matnum)
    if (matname==None) and (patname==None): return  # material/pattern already written
    if material:
        MATD = GET_MATERIAL_PROPS(material) # 'translate' property names
        st = "%s = s.newMaterial( 'standard', [\n" % matname
        st += "\t\t 'ka', vector3(%f, %f, %f),\n" % (MATD['R'], MATD['G'], MATD['B'])
    else:
        st = "WORLD_LIGHT = s.newMaterial( 'standard', [\n"
        st += "\t\t 'ka', vector3(%f, %f, %f),\n" % (WORLD_COLOR[0], WORLD_COLOR[1], WORLD_COLOR[2])
    if patname: st += "\t\t 'ka', %s,\n" % patname
    st += "\t\t 'kc', vector3(0.0, 0.0, 0.0),\n"
    st += "\t\t 'kd', 0.0,\n"
    # since this is used mostly as a pseudo lightsource, disable radiosity calc. (no light transport from other sources)
    st += "\t\t 'radiosity', 0,\n"
    st += "\t\t 'shadowing', 0.0" 
    # probably better not enable glitter for this material type
    #if Tglit_toggle.val: st += ",\n\t\t 'glitter', 1"
    st += "\n\t ] )\n\n"
    matfile.write(st)


# DIRECT MATSpiderLF MATERIAL IMPORT
# MATSpider Materials can be controlled (transform is used) by either the object itself or an empty.
# If an empty is used, this empty can either control all objects with this material (empty name: materialname_TEXC),
# or it can control the material for this object only (empty name: objectname_TEXC)
def WRITE_MATSPIDER(material, objectname, texture_control_list):
    global MATSPIDER_USECOUNT
    # The only material which can be duplicated, since the same texture can be used by different objects,
    # so the texture/pattern transform can be different for all of them
    matname = material.name
    dupmatname = matname
    try:
        MATSPIDER_USECOUNT[matname] += 1
        dupmatname += ('_%d' % MATSPIDER_USECOUNT[matname])
        

    except KeyError:
        # not in dictionary yet
        MATSPIDER_USECOUNT[matname] = 1
    # Material must be in 'Library' directory, name is matname - mat_id
    # Convert all to lowercase, MATSpider seems to expect materialname in lowercase, otherwise nothing happens...
    # Argument to MTL2PY must be only material name, internally expanded to correct full path
    mat_noid = matname[:-5]
    MSPNAME = (mat_noid+'.mtl').lower()
    # Get the 'pythonized' material from MATSpider,
    # use material name as block prefix for all MATSpider parameters
    # Function will raise appropriate error when anything goes wrong
    ps = MSPint.MTL2PY(MSPNAME, dupmatname)
    # If there is an empty used as a texture controller, write transform of empty,
    # otherwise use transform of object this material is linked with.
    # the latter is the only case where object animation data is duplicated, but is easiest solution at this point
    # LATER UPDATE: it doesn't matter what is used as a texture controller, it can now be another mesh too
    # The objects are put in the list here instead of in the ExportIt main object 'get' routine,
    # since this way the same order is preserved. (the same order as the meshlist)
    # First test texture control for material
    texc_name = mat_noid + '_TEXC'
    texc = Blender.Object.Get(texc_name)
    if texc:
        # material texture controller found
        print "MATSpider material %s has a texture control" % matname
        texture_control_list.append(texc_name)
    else:
        # no texture controller by material name, object name?
        texc_name = (objectname + '_TEXC')
        texc = Blender.Object.Get(texc_name)
        if texc:
            # The texture controller is for this object only
            print "Object %s has MATSpider texture control used for this object only" % objectname
            texture_control_list.append(texc_name)
        else:
            # No actual texture controller, use object transform and include objectname in texture control list for animation data export.
            # Only case of animation data duplication, since object data is later exported again,
            # but cannot be retrieved here yet, since the script at this point only expects texture control animation data
            print "Object %s itself is texture control for MATSpider material %s" % (objectname, matname)
            texc = Blender.Object.Get(objectname)
            # Use the meshlist name index to insert the object name in the correct order in the texture_control_list
            texture_control_list.append(objectname)
    if Tanimation.val==2:
        # SINGLE FILE ANIM SCRIPT
        desc = "TEXTURE CONTROL TRANSFORM FOR MATERIAL: " + dupmatname
        WriteAnimTransform(matfile, 0, 1, desc)
    else:
        # matrix now used directly
        bmtx = texc.matrix
        file.write("\n#### START TEXTURE TRANSFORM FOR MATERIAL: %s\n" % dupmatname)
        file.write("s.transformBegin(transform().setMatrix_rm( " + BMTX_TO_STRING(bmtx) + " ))\n")
    # Lines must be written separately, MSP uses newline char only, so add win32 linebreak
    # Parse lines for variable replacement, anything that starts with BLEND_
    # Check for unknown variable names
    # Also check if any comments are left after parsing from MATSpider: '<Plese write x type parameter>'
    contains_comment = 0
    unknown_vars = []
    # keep track of warnings, only do once
    WARN_NO_IPO = 0
    WARN_IPO_EMPTY = 0
    WARN_NO_CURVE = 0
    MATD = GET_MATERIAL_PROPS(material) # 'translate' property names
    for line in ps.splitlines():
        # make list of vars
        var_start = line.find('BLEND_')
        var_end = line.find(' =')
        if (var_start!=-1) and (var_end!=-1):
            # Blender variable found
            BLVAR = line[var_start:var_end]
            # find type
            #tp_start = line.find('write')
            #tp_end = line.find('type')
            #if (tp_start!=-1) and (tp_end!=-1): st += ': '+line[tp_start+6:tp_end-1]
            # replace with corresponding value from the specified Blender material parameter
            nline = line[:var_end+3]
            if BLVAR in MSP_BL_VARS.keys():
                # check for vector/color types
                if BLVAR=='BLEND_COLOR_RGB':
                    nline += "vector3(%f, %f, %f)" % (MATD['R'], MATD['G'], MATD['B'])

                elif BLVAR=='BLEND_COLOR_SPEC_RGB':
                        nline += "vector3(%f, %f, %f)" % (MATD['SPECR'], MATD['SPECG'], MATD['SPECB'])

                elif BLVAR=='BLEND_COLOR_MIR_RGB':
                    nline += "vector3(%f, %f, %f)" % (MATD['MIRR'], MATD['MIRG'], MATD['MIRB'])

                elif BLVAR=='BLEND_HARD':
                    # hardness parameter is integer in range 1-255, change to float <= 1.0
                    nline += "%f" % (MATD['HARD'] / 255.0)

                elif BLVAR=='BLEND_TIME':
                    # extra non-material parameter to be able to use the current frame/time value
                    # useful for smoke animations for instance
                    nline += "%f" % Blender>Get('curtime')

                else:
                    # translated with MSP dict.
                    exec(('mtval = material.'+MSP_BL_VARS[BLVAR]))
                    nline += ("%f" % mtval)
                matfile.write(nline + '\n')
            elif BLVAR in MSP_BL_VARS_IPO.keys():
                if BL_VERSION>223:
                    ipo = material.getIpo()
                else:
                    ipo = material.ipo
                if ipo:
                    if len(ipo.curves):
                        curvenames = []
                        for curve in ipo.curves: curvenames.append(curve.name)
                        thiscurve = MSP_BL_VARS_IPO[BLVAR]
                        if thiscurve in curvenames:
                            curve = ipo.curves[curvenames.index(thiscurve)]
                            # cvpsize = len(curve.points)   # was used to test for curve, probably not necessary...
                            nline += '%f' % Blender.Ipo.Eval(curve, Blender.Get('curtime'))
                            matfile.write(nline + '\n')
                        else:
                            # no curve found for this var, can warn multiple times, write line anyway, check for comments
                            matfile.write(line + '\n')
                            if line.find('<')!=-1: contains_comment = 1
                            st = "%s material requires IPO variable %s, but was not found" % (matname, MSP_BL_VARS_IPO[BLVAR])
                            MSPint.MsgBox(st, 0)
                    else:
                        # empty ipo (no curves), warn once, write anyway, check for comments in this line
                        matfile.write(line + '\n')
                        if line.find('<')!=-1: contains_comment = 1
                        if not WARN_IPO_EMPTY:
                            st = "%s requires IPO, but material IPO is empty (no curves)" % matname
                            MSPint.MsgBox(st, 0)
                            WARN_IPO_EMPTY = 1
                else:
                    # no ipo, warn once, write anyway, check for comments in this line
                    matfile.write(line + '\n')
                    if line.find('<')!=-1: contains_comment = 1
                    if not WARN_NO_IPO:
                        st = "%s uses IPO variables, but Blender material has no IPO!" % matname
                        MSPint.MsgBox(st, 0)
                        WARN_NO_IPO = 1
            else:
                # unknown variable found, just write it anyway, comments will still be there
                # remember it, to warn later
                unknown_vars.append(BLVAR)
                matfile.write(line + '\n')
        else:
            # no blender variable, comment which can't be replaced?
            if line.find('<')!=-1: contains_comment = 1
            matfile.write(line+'\n')
    # only do 'comments' warning if this is the first time for this material,
    # otherwise there could be x warnings when the same material is used on duplicated objects
    if contains_comment and MATSPIDER_USECOUNT[matname]==1:
        st = "MATSpider material definition for material %s contains comments, editing required!" % matname
        MSPint.MsgBox(st, 0)
    num_unknown = len(unknown_vars)
    if num_unknown:
        st = 'Unknown BLEND_ variables found:\n'
        for i in range(num_unknown):
            st += unknown_vars[i]
            if (i!=(num_unknown-1)): st += ', '
        st += "\nEditing required!"
        MSPint.MsgBox(st, 0)
    # write end of transform here, if there was a texture controller
    if texc:
        if Tanimation.val==2:
            WriteAnimTransform(matfile, 0, 0, desc)
        else:
            file.write("s.transformEnd()\n")
            file.write("### END TEXTURE TRANSFORM FOR MATERIAL: %s\n\n" % matname)
    # extra linebreak
    matfile.write('\n')


#######################################################################################################################################
# DIRECT MATERIAL IMPORT FROM BLENDFILES
# Easily the hardest part of all the code in this script, took weeks to figure out,
# and of course it still isn't quite correct, nor can it be, LF is not a Blender emulator after all,
# nevertheless, almost everything is handled in one way or another, whether it is correct or not...
# LATER NOTE: having now access to the original bLender source, it seems I was not far off on most occasions
# Of course it would have been better to just wait for the source instead of doing all those painstaking tests to find everything out for myself...

# create the LF texture pattern, this is a separate function since a single texture can be written twice (color & intensity)
def WRITE_LFTEXPAT(tp, mt, mtex, numpat, iscol):
    tx = mtex.tex
    st = "LFTEX%d = s.newPattern( 'map', [\n" % numpat
    if iscol:
        # the texture for colormapping (Col, Csp, Cmir, including Nor)
        st += "\t 'texture', LFIMG%d,\n" % BLENDFILE_LFIMG_LIST.index(tx.ima.id.name)
    else:
        # as intensity (Ref, Spec, Hard, Alpha, Emit)
        st += "\t 'texture', LFIMG%d,\n" % BLENDFILE_LFIMG_LIST.index('BW_'+tx.ima.id.name)
    st += "\t 'type', '%s',\n" % tp

    # The really hard (to figure out something LF compatible) texture scaling part
    # (part of it taken care of in texture transform)
    # XREPEAT/YREPEAT DOES NOT WORK THE SAME, NOT POSSIBLE IN LF, LF NEEDS FRAME-REPEAT OR SIMILAR...
    # JUST USED HERE FOR 'scale' PARAM. (except for flat/cube mapping))

    # if 'Rot90', direction is negative for uv & sphere, offset & size swapped too

    if (mtex.texco & 16):
        # 'surface', simpler offset and size, only xy used (uv-coords)
        sz = [mtex.size[0], mtex.size[1]]   # for the xxxxth time!!!, don't do list=list, you are modifying it!!!! (ok, OK, I'M SORRY!!)
        if (tx.imaflag & 16):
            sz[0], sz[1] = -sz[1], sz[0]
            ofs = [0.5 * (sz[0] - 1.0) - mtex.ofs[1], 0.5 * (sz[1] - 1.0) + mtex.ofs[0]]
        else:
            ofs = [0.5 * (sz[0] - 1.0) - mtex.ofs[0], 0.5 * (sz[1] - 1.0) + mtex.ofs[1]]
        if sz[0]!=0.0:
            sz[0] = 1.0/sz[0]
        else:
            sz[0] = 1.0e10
        if sz[1]!=0.0:
            sz[1] = 1.0/sz[1]
        else:
            sz[1] = 1.0e10
        st += "\t 'scale', vector2(%f, %f),\n" % (sz[0]/float(tx.xrepeat), sz[1]/float(tx.yrepeat))
        st += "\t 'offset', vector2(%f, %f),\n" % (ofs[0], ofs[1])
        if (tx.imaflag & 16):
            st += "\t 'rotation', %f,\n" % (pi*-0.5)
    else:
        if mtex.mapping in [0, 1]:  # 'Cube' not supported, pretend 'Flat'
            # in Blender setting x/yrepeat to a value other than 1, also disables clip in that direction
            # so if that happens, it is just interpreted as global
            if (tx.extend in [1,3]) or (tx.xrepeat>1) or (tx.yrepeat>1):
                # Extend, Repeat both interpreted as repeat
                # For Lightflow 500.0 seems to be the maximum scale value
                t = 500.0
                t2 = 2.0*t
                it2 = 1.0/t2
                st += "\t 'frame-offset', vector2(%f, %f),\n" % (-0.5-t, -0.5-t)
                st += "\t 'frame-scale', vector2(%f, %f),\n" % (t2, t2)
                # if 'Rot90' enabled, rotate 90 deg and scale x is negative
                if (tx.imaflag & 16):
                    st += "\t 'scale', vector2(%f, %f),\n" % (-it2, -it2)
                    st += "\t 'rotation', %f,\n" % (pi*0.5)
                else:
                    st += "\t 'scale', vector2(%f, %f),\n" % (it2, -it2)
            else:
                # Clip/ClipCube both interpreted as clip
                st += "\t 'frame-offset', vector2(-0.5, -0.5),\n"
                st += "\t 'frame-scale', vector2(1.0, 1.0),\n"
                # frame color is material color
                # does not really work as it should, since it really should behave like a alpha value
                st += "\t 'frame-color', vector3(%f, %f, %f),\n" % (mt.r, mt.g, mt.b)
                # if 'Rot90' enabled, rotate 90 deg and scale x is negative
                if (tx.imaflag & 16):
                    st += "\t 'scale', vector2(-1.0, -1.0),\n"  # x/yrep not used here, when used, disables clip in that direction
                    st += "\t 'rotation', %f,\n" % (pi*0.5)
                else:
                    st += "\t 'scale', vector2(1.0, -1.0),\n"   # x/yrep not used here, when used, disables clip in that direction
        else:   # sphere/tube, tube is LF 'cylinder' but doesn't work, another LF bug...
            sz = [mtex.size[0], mtex.size[1], mtex.size[2]]
            if tx.extend in [1,3]:  # Repeat, Extend
                # since blender scales with respect to center, and lightflow with one of the corners,
                # offset has to be calculated taking size into account
                # if 'Rot90' enabled, rotate -90 deg, scale x is negative, offset/size swapped
                if (tx.imaflag & 16):
                    sz[0], sz[1] = -sz[1], sz[0]
                    ofs = [0.5 * (sz[0] - 1.0) - mtex.ofs[1], 0.5 * (sz[1] - 1.0) + mtex.ofs[0]]
                else:
                    ofs = [0.5 * (sz[0] - 1.0) - mtex.ofs[0], 0.5 * (sz[1] - 1.0) + mtex.ofs[1]]
                if sz[0]!=0.0:
                    sz[0] = 1.0/sz[0]
                else:
                    sz[0] = 1.0e10
                if sz[1]!=0.0:
                    sz[1] = 1.0/sz[1]
                else:
                    sz[1] = 1.0e10
                st += "\t 'scale', vector2(%f, %f),\n" % (sz[0]/float(tx.xrepeat), sz[1]/float(tx.yrepeat))
                st += "\t 'offset', vector2(%f, %f),\n" % (ofs[0], ofs[1])
                if (tx.imaflag & 16):
                    st += "\t 'rotation', %f,\n" % (pi*-0.5)
            else:   # Clip, ClipCube
                # same as above, but more complicated
                if sz[0]==0.0: sz[0] = 0.001
                if sz[1]==0.0: sz[1] = 0.001
                t1, t2 = 1.0/sz[0], 1.0/sz[1]
                ofs = [t1 * (0.5 * (sz[0] - 1.0) - mtex.ofs[0]), t2 * (0.5 * (sz[1] - 1.0) + mtex.ofs[1])]
                st += "\t 'frame-scale', vector2(%f, %f),\n" % (t1, t2)
                st += "\t 'frame-offset', vector2(%f, %f),\n" % (ofs[0], ofs[1])
                # frame color is material color
                # does not really work as it should, since it really should behave like a alpha value
                st += "\t 'frame-color', vector3(%f, %f, %f),\n" % (mt.r, mt.g, mt.b)
                # if 'Rot90' enabled, rotate -90 deg and scale x is negative
                if (tx.imaflag & 16):
                    st += "\t 'scale', vector2(%f, %f),\n" % (-1.0/float(tx.xrepeat), 1.0/float(tx.yrepeat))
                    st += "\t 'rotation', %f,\n" % (pi*-0.5)
                else:
                    st += "\t 'scale', vector2(%f, %f),\n" % (1.0/float(tx.xrepeat), 1.0/float(tx.yrepeat))
    # in case it is used for bump/displacement mapping, set depth here
    # scaled by 1/100, LF can do pretty extreme bumpmapping
    # LF displacement is equivalent to negative Blender bumpmapping, so negate only when 'Nor' NOT negative
    t = mtex.norfac * -0.01
    if (mtex.maptoneg & 2): t *= -1.0
    st += "\t 'depth', %f\n" % t
    # needs ofs, size, to lf frame stuff here
    st += "] )\n"
    return st


def BLEND2LF(BFMOD, mt, objectname, TEXSPACE, CamOb, caustics):
    # create 'map' patterns from Material->MTex->Tex->Image

    global BLENDFILE_USECOUNT
    # The only other material which can be duplicated,
    # since the same material can be used by different objects, UNLESS it is Glob/Object/Refl mapped,
    # or only the material is used without textures,
    # otherwise the transform can be different for all of them.
    # HOWEVER: not the IMAGE texture itself, this can (and should) be written once, no matter how many times it is used.

    matname = mt.id.name[2:]    # don't include 'MA' id
    dupmatname = matname

    # test if any textures used at all, if so, set isglob to true if Glob/Object/Refl mapped
    tex_used = isglob = 0
    if mt.septex:
        mtex = mt.mtex[mt.texact]
        if (mtex!=None) and (mtex.mapto!=0) and ((mtex.texflag & 2)==0):
            tex_used = 1
            if mtex.texco in [2, 8, 32]: isglob = 1
    else:
        for idx in range(len(mt.mtex)):
            mtex = mt.mtex[idx]
            if (mtex!=None) and (mtex.mapto!=0) and ((mtex.texflag & 2)==0):
                tex_used += 1
                if mtex.texco in [2, 8, 32]: isglob += 1

    try:
        BLENDFILE_USECOUNT[matname] = (BLENDFILE_USECOUNT[matname][0]+1, (isglob==tex_used))
        dupmatname += ('_%d' % BLENDFILE_USECOUNT[matname][0])
        

    except KeyError:
        # not in dictionary yet
        BLENDFILE_USECOUNT[matname] = (1, (isglob==tex_used))

    # if the material is used more than once and it is all global, no need to write again
    if BLENDFILE_USECOUNT[matname][0]>1:
        if isglob==tex_used:
            # re-set the flag just in case no textures used at all,
            # must be done here, can't do before dictionary access
            BLENDFILE_USECOUNT[matname] = (BLENDFILE_USECOUNT[matname][0], 1)
            return

    st = "### START BLENDFILE MATERIAL: %s\n\n" % dupmatname

    # Now find and write images first when not written yet,
    # and remember them for later use when needed for other materials
    global BLENDFILE_LFIMG_LIST
    img_used = 0
    for idx in range(len(mt.mtex)):
        mtex = mt.mtex[idx]
        # empty channel?
        if mtex==None: continue
        # check if texture actually is used for anything (including stencilmode)
        if (mtex.mapto==0) and ((mtex.texflag & 2)==0): continue
        # sepT on? only export the activated texture channel
        if mt.septex and idx!=mt.texact: continue
        tx = mtex.tex
        if tx.type==8:
            if tx.ima:
                # if not written yet, write and save name in dict.
                # color and intens will be saved separately.
                colnm = tx.ima.id.name
                intnm = 'BW_' + colnm
                # as color tex? ('No RGB'/'Stencil' not enabled)
                if ((mtex.mapto & 15) or (mtex.maptoneg & 15)) and ((mtex.texflag & 3)==0) and (colnm not in BLENDFILE_LFIMG_LIST):
                    # Convert texture, ima.name is full path already, replace back with forward slashes in new path.
                    nm = TEXTURE_CONVERT(tx.ima.name).replace('\\', '/')
                    BLENDFILE_LFIMG_LIST.append(colnm)  # index will be used for LFIMG num.
                    st += "LFIMG%d = s.newTexture('%s')\n" % (BLENDFILE_LFIMG_LIST.index(colnm), nm)
                    img_used = 1
                # as intens tex? (or 'No RGB'/'Stencil' enabled)
                if ((mtex.mapto & 496) or (mtex.maptoneg & 496) or ((mtex.texflag & 3)!=0)) and (intnm not in BLENDFILE_LFIMG_LIST):
                    # 'BW_' will be put in front of output name in convert routine
                    intens_nm = TEXTURE_CONVERT(tx.ima.name, 1).replace('\\', '/')
                    BLENDFILE_LFIMG_LIST.append(intnm)
                    st += "LFIMG%d = s.newTexture('%s')\n" % (BLENDFILE_LFIMG_LIST.index(intnm), intens_nm)
                    img_used = 1

    if img_used:
        st += "\n"
        if PRINT_TRACE: print BLENDFILE_LFIMG_LIST

    # since LF 'cylinder' mapping doesn't seem to work, replace with 'sphere'
    # Blender 'Cube' also not supported, so use 'plane' mapping instead
    # Blender equiv: Flat       Cube     Tube       Sphere
    txmap_dict = {0:'plane', 1:'plane', 2:'sphere', 3:'sphere'}
    numpat = 0

    # create the Lightflow patterns to combine the Blender material textures
    col_used = nor_used = csp_used = cmr_used = ref_used = spec_used = emit_used = alpha_used = hard_used = 0

    # color texture used for Col/Nor/Csp/Cmir (unless 'No RGB' selected)
    last_colpat = last_norpat = last_csppat = last_cmrpat = 0
    # B&W intensity texture used for Ref/Spec/Hard/Alpha/Emit
    last_refpat = last_specpat = last_emitpat = last_alphapat = last_hardpat = 0
    # the actual textures
    last_coltex = last_intenstex = 0

    # bump/disp. map compose chain
    norpat_chain = []

    # hard pattern chain, pattern manipulation does not work for 'km'
    hardpat_chain = []

    stencil_used = last_stencilpat = 0

    for idx in range(len(mt.mtex)):
        mtex = mt.mtex[idx]

        # empty channel?
        if mtex==None: continue

        # check if texture actually is used for anything, including stencilmode
        if (mtex.mapto==0) and ((mtex.texflag & 2)==0): continue

        # sepT on? only export the activated texture channel
        # also ignore if the texture is stencil only without mapping
        if (mt.septex and (idx==mt.texact)) and ((mtex.mapto==0) and (mtex.texflag & 2)):
            continue
        if (mt.septex and (idx!=mt.texact)):
            continue

        tx = mtex.tex   # the actual texture

        # EVERY CHANNEL CAN HAVE IT'S OWN TRANSFORM (OBJECT,ORCO AND ENVIRONMENT MAPPING: ALL DIFF. TRNS.)
        # TRANSFORM SHOULD ONLY ENCOMPASS THE TEXTURE NOT THE COMPLETE MATERIAL.

        # write matrix of object to transform texture for orco/object/environment mapping
        transform_used = 0
        if (mtex.texco==1):
            # orco mapping, use object transform to place texture
            # instead of using the matrix of the blendfile, use the matrix of the actual object
            # This is necessary otherwise animation would not be possible
            bmtx = Blender.Object.Get(objectname).matrix
            # set translation point to texturespace center
            # DON'T MODIFY ORIGINAL MATRIX, list==list!!!
            texmtx = [list(bmtx[0])] + [list(bmtx[1])] + [list(bmtx[2])] + [list(TEXSPACE[1]) + [bmtx[3][3]]]
            st += "s.transformBegin(transform().setMatrix_rm( " + BMTX_TO_STRING(texmtx) + " ))\n"
            transform_used = 1
        elif mtex.texco in [2, 32]:
            # object or environment mapping, use the transform of the specified object or camera
            if mtex.object==None or (mtex.texco==2):
                # no object specified or environment mapping, use camera matrix as in Blender
                # (cam.mtx seems to be default without specifying object for obj.mapping)
                bmtx = CamOb.matrix
            else:
                # again as above, not from blendfile anymore, but the blender matrix directly to allow animation
                bmtx = Blender.Object.Get(mtex.object.id.name[2:]).matrix
            st += "s.transformBegin(transform().setMatrix_rm( " + BMTX_TO_STRING(bmtx) + " ))\n"
            transform_used = 1

        # Start with creating transforms to map texture from Lightflow global to Blender 'mapping'
        if (mtex.texco & 16)==0:    # not used for 'surface' (uv-coords)
            if mtex.mapping in [0, 1]:  # Flat/Cube, 'Cube' not supported, pretend 'Flat'
                # uses mesh boundbox as texturespace
                sz = [mtex.size[0]*tx.xrepeat, mtex.size[1]*tx.yrepeat, mtex.size[2]]
                # This is just a hack for x/yrep, and most of the time will not work (only when size is integ.),
                # simply because LF really needs a 'frame-repeat' param. to be able to really simulate this..
                if (tx.xrepeat>1) or (tx.yrepeat>1):
                    sz2 = [sz[0], sz[1], sz[2]] # REMEMBER, DONT DO list = list, ALWAYS COPY EVERY ELEM.!!
                    if sz2[0]!=0.0: sz2[0] = 1.0/sz2[0]
                    if sz2[1]!=0.0: sz2[1] = 1.0/sz2[1]
                    ofs = [ 0.5 * (sz[0] - 1.0) + mtex.ofs[0], - sz2[0],
                            0.5 * (sz[1] - 1.0) + mtex.ofs[1], - sz2[1],
                            0.5 * (sz[2] - 1.0) + mtex.ofs[2]]
                else:
                    ofs = [mtex.ofs[0], mtex.ofs[1], mtex.ofs[2]]
                # if the size is exactly 0, the LF result is completely different from Blender, so use a very small value instead
                # and since the inverse is used, this would actually be a very large value...
                if sz[0]!=0.0:
                    sz[0] = 1.0/sz[0]
                else:
                    sz[0] = 1.0e10  # probably large enough
                if sz[1]!=0.0:
                    sz[1] = 1.0/sz[1]
                else:
                    sz[1] = 1.0e10
                if sz[2]!=0.0:
                    sz[2] = 1.0/sz[2]
                else:
                    sz[2] = 1.0e10
                # TEXSPACE NOT NEEDED FOR GLOBAL/OBJECT/ENVIRONMENT MAPPING, IS HOWEVER TWICE THE SIZE NEEDED
                if mtex.texco in [2, 8, 32]:
                    st += "\ns.transformBegin(transform().scaling( vector3(%f, %f, %f) ))\n" % (2.0*sz[0], 2.0*sz[1], 2.0*sz[2])
                else:
                    st += "\ns.transformBegin(transform().scaling( vector3(%f, %f, %f) ))\n" % (TEXSPACE[0][0]*sz[0], TEXSPACE[0][1]*sz[1], TEXSPACE[0][2]*sz[2])
                if tx.type==5: ofs[0] += 0.5    # blend is translated on x-axis by 0.5
                st += "s.transformBegin(transform().translation( vector3(%f, %f, %f) ))\n" % (-ofs[0], -ofs[1], -ofs[2])
            else:
                # sphere/cylinder, TEXSPACE size only, NOT for global-/object-/environment-mapping
                st += "\n"
                if mtex.texco not in [2, 8, 32]:
                    st += "s.transformBegin(transform().scaling( vector3(%f, %f, %f) ))\n" % (TEXSPACE[0][0], TEXSPACE[0][1], TEXSPACE[0][2])

        # the mapping axis transform,
        # only works for disabling/swapping axes, setting any two or more to the same axis doesn't work...
        # Omit if default settings: x==x,y==y,z==z
        axistrans = 0
        if (mtex.projx!=1) or (mtex.projy!=2) or (mtex.projz!=3):
            # matrix, if any axis is disabled, the axis is not set to zero,
            # but a very large value instead, otherwise the result will not be the same
            projmtx = [ [0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 1.0]]
            # x-axis
            if mtex.projx!=0:
                projmtx[0][mtex.projx-1] = 1.0
            else:
                projmtx[0][0] = 1.0e10
            # y-axis
            if mtex.projy!=0:
                projmtx[1][mtex.projy-1] = 1.0
            else:
                projmtx[1][1] = 1.0e10
            # z-axis
            if mtex.projz!=0:
                projmtx[2][mtex.projz-1] = 1.0
            else:
                projmtx[2][2] = 1.0e10
            st += "s.transformBegin(transform().setMatrix_rm( " + BMTX_TO_STRING(projmtx) + " ))\n"
            axistrans = 1

        # sphere tex. rotation placed here, must be first
        if mtex.mapping in [2,3]:   # 'Tube' or 'Sphere' ---- NOTE: LF CYLINDER MAPPING DOESN'T SEEM TO WORK!!
            # Sphere, is rotated around Z axis by -90
            st += "s.transformBegin(transform().rotationAroundZ( %f ) )\n" % (-0.5*pi)

        if tx.type==8:
            # 'Image' texture
            if tx.ima:

                if (mtex.texco & 16):
                    # uv is activated
                    tp = 'surface'
                else:
                    tp = txmap_dict[mtex.mapping]

                # color texture, unless 'Stencil' or 'No RGB' enabled, then use intens.
                if ((mtex.mapto & 15) or (mtex.maptoneg & 15)) and ((mtex.texflag & 3)==0):
                    numpat += 1
                    st += WRITE_LFTEXPAT(tp, mt, mtex, numpat, 1)

                    # brightness/contrast/color changes, only when (bri | con | txrgb) != 1
                    if (tx.bright!=1.0) or (tx.contrast!=1.0) or (tx.rfac!=1.0) or (tx.gfac!=1.0) or (tx.bfac!=1.0):
                        # grey
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('tint', ['color', vector3(0.5, 0.5, 0.5) ])\n" % numpat
                        # tex - grey
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('sub', ['patterns', LFTEX%d, LFTEX%d] )\n" % (numpat, numpat-2, numpat-1)
                        # texrgb * contrast
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (numpat, tx.contrast*tx.rfac, tx.contrast*tx.gfac, tx.contrast*tx.bfac)
                        # (tex-grey)*contrast*texrgb
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('mul', ['patterns', LFTEX%d, LFTEX%d] )\n" % (numpat, numpat-2, numpat-1)
                        # texrgb * brightness
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (numpat, tx.bright*tx.rfac, tx.bright*tx.gfac, tx.bright*tx.bfac)
                        # (tex-grey)*contrast*texrgb + brightness*texrgb (prev. 2 pat.)
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('add', ['patterns', LFTEX%d, LFTEX%d] )\n" % (numpat, numpat-2, numpat-1)
                        # 0.5*texrgb
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (numpat, 0.5*tx.rfac, 0.5*tx.gfac, 0.5*tx.bfac)
                        # finally: (tex-grey)*contrast*texrgb + brightness*texrgb - 0.5*texrgb(prev. 2 pat.)
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('sub', ['patterns', LFTEX%d, LFTEX%d] )\n" % (numpat, numpat-2, numpat-1)

                    # if 'Neg' is enabled, invert the color pattern
                    if (mtex.texflag & 4):
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('not', ['pattern', LFTEX%d] )\n" % (numpat, numpat-1)

                    # update 'pointers' for later use
                    if (mtex.mapto & 2) or (mtex.maptoneg & 2): last_norpat = numpat
                    last_coltex = numpat

                if (mtex.mapto & 496) or (mtex.maptoneg & 496) or ((mtex.texflag & 3)!=0):
                    # intensity texture
                    numpat += 1
                    st += WRITE_LFTEXPAT(tp, mt, mtex, numpat, 0)

                    # brightness/contrast/color changes, only when (bri | con | texrgb) != 1
                    if (tx.bright!=1.0) or (tx.contrast!=1.0) or (tx.rfac!=1.0) or (tx.gfac!=1.0) or (tx.bfac!=1.0):
                        # here texrgb as avg.int.
                        avtxrgb = (tx.rfac + tx.gfac + tx.bfac) / 3.0
                        # grey
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('tint', ['color', vector3(0.5, 0.5, 0.5) ])\n" % numpat
                        # tex - grey
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('sub', ['patterns', LFTEX%d, LFTEX%d] )\n" % (numpat, numpat-2, numpat-1)
                        # texrgb * contrast
                        numpat += 1
                        t = avtxrgb * tx.contrast
                        st += "LFTEX%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (numpat, t, t, t)
                        # (tex-grey)*contrast*texrgb
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('mul', ['patterns', LFTEX%d, LFTEX%d] )\n" % (numpat, numpat-2, numpat-1)
                        # texrgb * brightness
                        numpat += 1
                        t = avtxrgb * tx.bright
                        st += "LFTEX%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (numpat, t, t, t)
                        # (tex-grey)*contrast*texrgb + brightness*texrgb (prev. 2 pat.)
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('add', ['patterns', LFTEX%d, LFTEX%d] )\n" % (numpat, numpat-2, numpat-1)
                        # 0.5*texrgb
                        numpat += 1
                        t = 0.5*avtxrgb
                        st += "LFTEX%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (numpat, t, t, t)
                        # finally: (tex-grey)*contrast*texrgb + brightness*texrgb - 0.5*texrgb(prev. 2 pat.)
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('sub', ['patterns', LFTEX%d, LFTEX%d] )\n" % (numpat, numpat-2, numpat-1)

                    # if 'Neg' is enabled, invert the intensity pattern
                    if (mtex.texflag & 4):
                        numpat += 1
                        st += "LFTEX%d = s.newPattern('not', ['pattern', LFTEX%d] )\n" % (numpat, numpat-1)

                    # update 'pointers' for later use
                    last_intenstex = numpat
                    if ((mtex.texflag & 3)!=0): last_coltex = numpat

        elif tx.type in [1,2,3, 6]:
            # Clouds/Wood/Marble or Stucci, Stucci is here just the nor-mapped version of clouds
            numpat += 1
            pt = {1:'multifractal', 2:'wood', 3:'marble', 6:'multifractal'}
            # colorclouds?
            if (tx.type==1) and (tx.stype==1): pt[1] = 'multifractal-RGB'
            st += "LFTEX%d = s.newPattern('%s', [\n" % (numpat, pt[tx.type])
            if tx.flag:
                # colorband, alpha not used in LF
                coba = tx.coba
                for i in range(coba.tot):
                    dt = coba.data[i]
                    vst = "vector3(%f, %f, %f)" % (dt.r, dt.g, dt.b)
                    st += "\t 'color', %f, %s, %s,\n" % (dt.pos, vst, vst)
            else:
                # cyclic bw (should include alpha to fully emulate Blender)
                vst = "vector3(0.0, 0.0, 0.0)"
                st += "\t 'color', 0.0, %s, %s,\n" % (vst, vst)
                vst = "vector3(1.0, 1.0, 1.0)"
                st += "\t 'color', 0.5, %s, %s,\n" % (vst, vst)
                vst = "vector3(0.0, 0.0, 0.0)"
                st += "\t 'color', 1.0, %s, %s,\n" % (vst, vst)
            st += "\t 'scale', %f,\n" % (tx.noisesize * 0.5)    # looks more similar
            # the depth value for the bump/displacement factor, see above
            t = mtex.norfac * -0.01
            if (mtex.maptoneg & 2): t *= -1.0
            # same for stucci wall in/out
            if (tx.type==6) and (tx.stype==2): t *= -1.0
            st += "\t 'depth', %f,\n" % t
            # only clouds and marble use noisedepth
            if tx.type in [1,3]: st += "\t 'turbulence.octaves', %d" % (1+tx.noisedepth)
            if tx.type==1:
                # clouds, multifractal is without distortion
                if tx.noisetype==0:
                    st += ",\n\t 'basis', 'normal'"
                else:
                    st += ",\n\t 'basis', 'log'"
                st += ",\n\t 'turbulence.distortion', 0.0"
            # only wood and marble use turbulence (scaled to 0-1)
            elif tx.type==2:
                # wood, only uses noise when BandNoise or RingNoise enabled
                if tx.stype>1:
                    st += "\t 'turbulence.amount', %f" % tx.turbul
                else:
                    st += "\t 'turbulence.amount', 0.0"
            elif tx.type==3:
                # marble
                st += ",\n\t 'turbulence.omega', %f" % (tx.turbul * 5.0e-3)
            elif tx.type==6:
                # Stucci, as two octave multifractal
                if tx.stype==0:
                    st += "\t 'basis', 'normal'"
                else:   # wall in/out, reverse is done above with depth value
                    st += "\t 'basis', 'log'"
                st += ",\n\t 'turbulence.distortion', %f" % tx.turbul
                st += ",\n\t 'turbulence.octaves', 2"
            st += "\n ] )\n"
            last_coltex = last_intenstex = numpat

        elif tx.type==5:
            # Blend, sphere/halo not supported yet, although could be done with 'radial' pattern
            numpat += 1
            if tx.stype in [0,1,2,3]:
                # Lin, Quad, Ease, Diag
                if tx.stype==3:
                    # Diag, rotate 45 degrees around all axes
                    st += "s.transformBegin(transform().rotationAroundY( %f ))\n" % (0.25*pi)
                else:
                    # Lin, Quad, Ease, rotate -90 around Y-axis
                    st += "s.transformBegin(transform().rotationAroundY( %f ))\n" % (0.5*pi)
                st += "LFTEX%d = s.newPattern('linear-z', [\n" % numpat
                if tx.flag:
                    # colorband, alpha not used in LF
                    # this will only behave as 'linear', should really be multiply with basic gradient
                    coba = tx.coba
                    for i in range(coba.tot):
                        dt = coba.data[i]
                        vst = "vector3(%f, %f, %f)" % (dt.r, dt.g, dt.b)
                        st += "\t 'color', %f, %s, %s,\n" % (dt.pos, vst, vst)
                else:
                    # standard bw gradient
                    # X value (position)
                    ps = [0.0, 0.25, 0.5, 0.75, 1.0]
                    # brightness, standard is linear, reverse order
                    br = [1.0, 0.75, 0.5, 0.25, 0.0]
                    if tx.stype==1:
                        # Quadractic
                        br = [b*b for b in br]
                    elif tx.stype==2:
                        # Ease, guess
                        br = [b*b*(3.0-2.0*b) for b in br]
                    for i in range(len(br)):
                        vst = "vector3(%f, %f, %f)" % (br[i], br[i], br[i])
                        st += "\t 'color', %f, %s, %s,\n" % (ps[i], vst, vst)
                st += "\t 'scale', 1.0\n"
                st += "] )\n\n"
                st += "s.transformEnd()\n"

            last_coltex = last_intenstex = numpat

        # end mapping axis transform
        if axistrans: st += "s.transformEnd()\n"

        # end placement texture transform (Flat/Cube/Tube/Sphere, not uv)
        if (mtex.texco & 16)==0:
            if mtex.mapping in [0, 1]:
                # Flat/Cube
                st += 2*"s.transformEnd()\n"
            else:
                # Sphere/Cylinder
                st += "s.transformEnd()\n"
                # extra transform not for global-/object-/environment-mapping
                if mtex.texco not in [2, 8, 32]:
                    st += "s.transformEnd()\n"

        st += "\n"

        if mtex.texco & 2:
            # Reflection/Environment mapping enabled
            numpat += 1
            st += "LFTEX%d = s.newPattern('envmap', [\n" % numpat
            st += "\t 'pattern', LFTEX%d,\n" % (numpat-1)
            st += "\t 'center', vector3(0.0, 0.0, 0.0),\n"
            st += "\t 'radius', 1.0,\n"
            st += "\t 'reflection', vector3(1.0, 1.0, 1.0),\n"
            st += "\t 'infinite-size', 1\n"
            st += "] )\n\n"
            if tx.type==8:
                if (mtex.mapto & 15) or (mtex.maptoneg & 15):
                    last_coltex = numpat
                if (mtex.mapto & 496) or (mtex.maptoneg & 496):
                    last_intenstex = numpat
            elif tx.type in [1,2,3]:
                last_colpat = last_norpat = last_csppat = last_cmrpat = numpat
                last_refpat = last_specpat = last_emitpat = last_alphapat = last_hardpat = numpat
                last_coltex = last_intenstex = numpat

        # end texture transform
        if transform_used: st += "s.transformEnd()\n\n"

        # texture used for bumpmapping, independent of blendtype, just use compose later
        # no other parameter but norfac is used
        # if first normap, use last texture directly
        # negative nor is handled in texture above (depth value)
        if (mtex.mapto & 2) or (mtex.maptoneg & 2):
            # last (non-negative) pattern is norpat
            norpat_chain.append(last_coltex)
            nor_used = 1

        # TEXTURE MIXING
        # Almost total rewrite from source to make sure it matches 100% (probably more like 75% or less though...)
        # Hard does not work with anything but the texture itself, so result is not the same as Blender,
        # Alpha is faked with IOR 1.0 + refr.col modulation, but should ideally also mod. dif.col w. inverse alpha (todo, or maybe not...)

        if (mtex.texflag & 2):
            # stencil mode
            numpat += 1
            last_stencilpat += 1
            st += "LFSTC%d = LFTEX%d\n\n" % (last_stencilpat, last_intenstex)
            stencil_used = 1

        if (mtex.mapto & 1):    # Col, does not use maptoneg
            # texture used for colormapping, was correct first time (except for 'No RGB'),

            # matcol is only material color when first time use of colchan., otherwise it is previous colorchannel
            if not col_used:
                numpat += 1
                last_colpat += 1
                st += "LFCOL%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_colpat, mt.r, mt.g, mt.b)
            else:
                last_colpat += 1
                st += "LFCOL%d = LFCOL%d\n" % (last_colpat, last_colpat-1)
            matcol = last_colpat

            # last texture
            last_colpat += 1
            st += "LFCOL%d = LFTEX%d\n" % (last_colpat, last_coltex)

            norgb = 0
            if (mtex.texflag & 1) or stencil_used:
                # No RGB, use intensity instead
                numpat += 1
                last_colpat += 1
                if stencil_used:
                    st += "LFCOL%d = LFCOL%d\n" % (last_colpat, last_colpat-1)
                else:
                    st += "LFCOL%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_colpat, mtex.r, mtex.g, mtex.b)
                norgb = 1

            # fact
            numpat += 1
            last_colpat += 1
            fact_pat = last_colpat
            t = mtex.colfac
            st += "LFCOL%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_colpat, t, t, t)
            # *Tin, which is intensity if 'No RGB' enabled, otherwise one, so nothing to be done
            if norgb:
                # No RGB, fact*Tin = fact*intensity, texture is already intensity, so multiply with texture
                numpat += 1
                last_colpat += 1
                fact_pat = last_colpat
                if stencil_used:
                    st += "LFCOL%d = s.newPattern('mul', ['patterns', LFSTC%d, LFCOL%d] )\n" % (last_colpat, last_stencilpat, last_colpat-1)
                else:
                    st += "LFCOL%d = s.newPattern('mul', ['patterns', LFCOL%d, LFCOL%d] )\n" % (last_colpat, last_colpat-3, last_colpat-1)

            # facm, as 'not' of fact, instead of 1-colfac, since Tin multiply could have been done before,
            # except for 'Mul' which IS 1-colfac
            if mtex.blendtype<2:    # add/sub don't use facm
                numpat += 1
                last_colpat += 1
                facm_pat = last_colpat
                if mtex.blendtype==1:
                    # for 'Mul', facm=1-colfac
                    t = 1.0-mtex.colfac
                    st += "LFCOL%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_colpat, t, t, t)
                else:
                    st += "LFCOL%d = s.newPattern('not', ['pattern', LFCOL%d] )\n" % (last_colpat, fact_pat)

            # all modes common, fact * tex
            numpat += 1
            last_colpat += 1
            st += "LFCOL%d = s.newPattern('mul', ['patterns', LFCOL%d, LFCOL%d] )\n" % (last_colpat, last_colpat-3-norgb+(mtex.blendtype>1), fact_pat)

            if mtex.blendtype==0:   # Mix
                # facm * matcol
                numpat += 1
                last_colpat += 1
                st += "LFCOL%d = s.newPattern('mul', ['patterns', LFCOL%d, LFCOL%d] )\n" % (last_colpat, facm_pat, matcol)
                # fact*tex + facm*matcol
                numpat += 1
                last_colpat += 1
                st += "LFCOL%d = s.newPattern('add', ['patterns', LFCOL%d, LFCOL%d] )\n" % (last_colpat, last_colpat-2, last_colpat-1)
            elif mtex.blendtype==1: # Mul
                # fact*tex + facm
                numpat += 1
                last_colpat += 1
                st += "LFCOL%d = s.newPattern('add', ['patterns', LFCOL%d, LFCOL%d] )\n" % (last_colpat, facm_pat, last_colpat-1)
                # prev. * matcol
                numpat += 1
                last_colpat += 1
                st += "LFCOL%d = s.newPattern('mul', ['patterns', LFCOL%d, LFCOL%d] )\n" % (last_colpat, last_colpat-1, matcol)
            else:   # Add/Sub
                # fact*tex + matcol
                numpat += 1
                last_colpat += 1
                if mtex.blendtype==2:
                    mode = 'add'
                else:
                    mode = 'sub'
                st += "LFCOL%d = s.newPattern('%s', ['patterns', LFCOL%d, LFCOL%d] )\n" % (last_colpat, mode, matcol, last_colpat-1)

            st += "\n"

            col_used = 1
    
        if (mtex.mapto & 4):    # Csp, does not use maptoneg
            # texture used for specular colormapping

            # matcsp is only material specular color when first time use of cspchan., otherwise it is last csppat
            if not csp_used:
                numpat += 1
                last_csppat += 1
                st += "LFCSP%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_csppat, mt.specr, mt.specg, mt.specb)
            else:
                last_csppat += 1
                st += "LFCSP%d = LFCSP%d\n" % (last_csppat, last_csppat-1)
            matcsp = last_csppat

            # last texture
            last_csppat += 1
            st += "LFCSP%d = LFTEX%d\n" % (last_csppat, last_coltex)

            norgb = 0
            if (mtex.texflag & 1):
                # No RGB, use intensity instead
                numpat += 1
                last_csppat += 1
                st += "LFCSP%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_csppat, mtex.r, mtex.g, mtex.b)
                norgb = 1

            # fact
            numpat += 1
            last_csppat += 1
            fact_pat = last_csppat
            t = mtex.colfac
            st += "LFCSP%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_csppat, t, t, t)
            # *Tin, which is intensity if 'No RGB' enabled, otherwise one, so nothing to be done
            if norgb:
                # No RGB, fact*Tin = fact*intensity, texture is already intensity, so multiply with texture
                numpat += 1
                last_csppat += 1
                fact_pat = last_csppat
                st += "LFCSP%d = s.newPattern('mul', ['patterns', LFCSP%d, LFCSP%d] )\n" % (last_csppat, last_csppat-3, last_csppat-1)

            # facm, as 'not' of fact, instead of 1-colfac, since Tin multiply could have been done before,
            # except for 'Mul' which IS 1-colfac
            if mtex.blendtype<2:    # not used for add/sub
                numpat += 1
                last_csppat += 1
                facm_pat = last_csppat
                if mtex.blendtype==1:
                    # for 'Mul', facm=1-colfac
                    t = 1.0-mtex.colfac
                    st += "LFCSP%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_csppat, t, t, t)
                else:
                    st += "LFCSP%d = s.newPattern('not', ['pattern', LFCSP%d] )\n" % (last_csppat, fact_pat)

            isub = 0
            if mtex.blendtype==3:
                # for 'Sub', fact = -fact, has to be done here, can't use 'sub' pat below, result is not the same
                numpat += 1
                last_csppat += 1
                st += "LFCSP%d = s.newPattern('tint', ['color', vector3(-1.0, -1.0, -1.0)] )\n" % last_csppat
                numpat += 1
                last_csppat += 1
                st += "LFCSP%d = s.newPattern('mul', ['patterns', LFCSP%d, LFCSP%d] )\n" % (last_csppat, fact_pat, last_csppat-1)
                fact_pat = last_csppat
                isub = 1

            # all modes common, fact * tex
            numpat += 1
            last_csppat += 1
            st += "LFCSP%d = s.newPattern('mul', ['patterns', LFCSP%d, LFCSP%d] )\n" % (last_csppat, last_csppat-3-norgb-isub*2+(mtex.blendtype>1), fact_pat)

            if mtex.blendtype==0:   # Mix
                # facm * matcsp
                numpat += 1
                last_csppat += 1
                st += "LFCSP%d = s.newPattern('mul', ['patterns', LFCSP%d, LFCSP%d] )\n" % (last_csppat, facm_pat, matcsp)
                # fact*tex + facm*matcsp
                numpat += 1
                last_csppat += 1
                st += "LFCSP%d = s.newPattern('add', ['patterns', LFCSP%d, LFCSP%d] )\n" % (last_csppat, last_csppat-2, last_csppat-1)
            elif mtex.blendtype==1: # Mul
                # fact*tex + facm
                numpat += 1
                last_csppat += 1
                st += "LFCSP%d = s.newPattern('add', ['patterns', LFCSP%d, LFCSP%d] )\n" % (last_csppat, facm_pat, last_csppat-1)
                # prev. * matcsp
                numpat += 1
                last_csppat += 1
                st += "LFCSP%d = s.newPattern('mul', ['patterns', LFCSP%d, LFCSP%d] )\n" % (last_csppat, last_csppat-1, matcsp)
            else:   # Add/Sub
                # fact*tex + matcsp, fact negated above for sub
                numpat += 1
                last_csppat += 1
                st += "LFCSP%d = s.newPattern('add', ['patterns', LFCSP%d, LFCSP%d] )\n" % (last_csppat, matcsp, last_csppat-1)

            st += "\n"

            csp_used = 1

        if (mtex.mapto & 8):    # Cmir, does not use maptoneg
            # DOES NOT WORK AS IT SHOULD

            # (unlike others) matcmr is BLACK when first time use of cmrchan., otherwise it is last cmrpat
            if not cmr_used:
                numpat += 1
                last_cmrpat += 1
                st += "LFCMR%d = s.newPattern('tint', ['color', vector3(0.0, 0.0, 0.0)] )\n" % last_cmrpat
            else:
                last_cmrpat += 1
                st += "LFCMR%d = LFCMR%d\n" % (last_cmrpat, last_cmrpat-1)
            matcmr = last_cmrpat

            # last texture
            last_cmrpat += 1
            st += "LFCMR%d = LFTEX%d\n" % (last_cmrpat, last_coltex)

            norgb = 0
            if (mtex.texflag & 1):
                # No RGB, use intensity instead
                numpat += 1
                last_cmrpat += 1
                st += "LFCMR%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_cmrpat, mtex.r, mtex.g, mtex.b)
                norgb = 1

            # fact
            numpat += 1
            last_cmrpat += 1
            fact_pat = last_cmrpat
            t = mtex.colfac
            st += "LFCMR%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_cmrpat, t, t, t)
            # *Tin, which is intensity if 'No RGB' enabled, otherwise one, so nothing to be done
            if norgb:
                # No RGB, fact*Tin = fact*intensity, texture is already intensity, so multiply with texture
                numpat += 1
                last_cmrpat += 1
                fact_pat = last_cmrpat
                st += "LFCMR%d = s.newPattern('mul', ['patterns', LFCMR%d, LFCMR%d] )\n" % (last_cmrpat, last_cmrpat-3, last_cmrpat-1)

            # facm, as 'not' of fact, instead of 1-colfac, since Tin multiply could have been done before,
            # except for 'Mul' which IS 1-colfac
            if mtex.blendtype<2:    # not used for add/sub
                numpat += 1
                last_cmrpat += 1
                facm_pat = last_cmrpat
                if mtex.blendtype==1:
                    # for 'Mul', facm=1-colfac
                    t = 1.0-mtex.colfac
                    st += "LFCMR%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_cmrpat, t, t, t)
                else:
                    st += "LFCMR%d = s.newPattern('not', ['pattern', LFCMR%d] )\n" % (last_cmrpat, fact_pat)

            isub = 0
            if mtex.blendtype==3:
                # for 'Sub', fact = -fact, has to be done here, can't use 'sub' pat below, result is not the same
                numpat += 1
                last_cmrpat += 1
                st += "LFCMR%d = s.newPattern('tint', ['color', vector3(-1.0, -1.0, -1.0)] )\n" % last_cmrpat
                numpat += 1
                last_cmrpat += 1
                st += "LFCMR%d = s.newPattern('mul', ['patterns', LFCMR%d, LFCMR%d] )\n" % (last_cmrpat, fact_pat, last_cmrpat-1)
                fact_pat = last_cmrpat
                isub = 1

            # all modes common, fact * tex
            numpat += 1
            last_cmrpat += 1
            st += "LFCMR%d = s.newPattern('mul', ['patterns', LFCMR%d, LFCMR%d] )\n" % (last_cmrpat, last_cmrpat-3-norgb-isub*2+(mtex.blendtype>1), fact_pat)

            if mtex.blendtype==0:   # Mix
                # facm * matcmr
                numpat += 1
                last_cmrpat += 1
                st += "LFCMR%d = s.newPattern('mul', ['patterns', LFCMR%d, LFCMR%d] )\n" % (last_cmrpat, facm_pat, matcmr)
                # fact*tex + facm*matcmr
                numpat += 1
                last_cmrpat += 1
                st += "LFCMR%d = s.newPattern('add', ['patterns', LFCMR%d, LFCMR%d] )\n" % (last_cmrpat, last_cmrpat-2, last_cmrpat-1)
            elif mtex.blendtype==1: # Mul
                # fact*tex + facm
                numpat += 1
                last_cmrpat += 1
                st += "LFCMR%d = s.newPattern('add', ['patterns', LFCMR%d, LFCMR%d] )\n" % (last_cmrpat, facm_pat, last_cmrpat-1)
                # prev. * matcmr
                numpat += 1
                last_cmrpat += 1
                st += "LFCMR%d = s.newPattern('mul', ['patterns', LFCMR%d, LFCMR%d] )\n" % (last_cmrpat, last_cmrpat-1, matcmr)
            else:   # Add/Sub
                # fact*tex + matcmr, fact negated above for sub
                numpat += 1
                last_cmrpat += 1
                st += "LFCMR%d = s.newPattern('add', ['patterns', LFCMR%d, LFCMR%d] )\n" % (last_cmrpat, matcmr, last_cmrpat-1)

            st += "\n"

            cmr_used = 1

        # FROM HERE INTENSITY TEXTURE IS USED (Ref/Spec/Hard/Alpha/Emit)
        # For 'Sub' mode, in source a check is done for <0, and limiting the value accordingly
        # here that is ommited for now, although might be possible to emulate using the 'less-than'/'greater-than' LF patterns
        # The result can therefore currently differ quite a bit, especially with layered 'Sub's

        if (mtex.mapto & 16) or (mtex.maptoneg & 16):   # Ref, does use maptoneg
            # Ref is modulation of diffuse color

            # matref is only material ref when first time use of refchan., otherwise it is last refpat
            if not ref_used:
                numpat += 1
                last_refpat += 1
                st += "LFREF%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_refpat, mt.ref, mt.ref, mt.ref)
            else:
                last_refpat += 1
                st += "LFREF%d = LFREF%d\n" % (last_refpat, last_refpat-1)
            matref = last_refpat

            # last intensity texture
            last_refpat += 1
            st += "LFREF%d = LFTEX%d\n" % (last_refpat, last_intenstex)

            # fact
            numpat += 1
            last_refpat += 1
            fact_pat = last_refpat
            t = mtex.varfac
            st += "LFREF%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_refpat, t, t, t)
            # *Tin, which is intensity, texture is already intensity, so multiply with texture
            numpat += 1
            last_refpat += 1
            fact_pat = last_refpat
            st += "LFREF%d = s.newPattern('mul', ['patterns', LFREF%d, LFREF%d] )\n" % (last_refpat, last_refpat-2, last_refpat-1)

            # facm, as 'not' of fact
            numpat += 1
            last_refpat += 1
            facm_pat = last_refpat
            st += "LFREF%d = s.newPattern('not', ['pattern', LFREF%d] )\n" % (last_refpat, fact_pat)

            if mtex.blendtype==1:
                # for 'Mul', facmul = 1-varfac
                numpat += 1
                last_refpat += 1
                t = 1.0-mtex.varfac
                st += "LFREF%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_refpat, t, t, t)
                facmul_pat = last_refpat

            if mtex.blendtype==3:
                # for 'Sub', fact = -fact, has to be done here, can't use 'sub' pat below, result is not the same
                numpat += 1
                last_refpat += 1
                st += "LFREF%d = s.newPattern('tint', ['color', vector3(-1.0, -1.0, -1.0)] )\n" % last_refpat
                numpat += 1
                last_refpat += 1
                st += "LFREF%d = s.newPattern('mul', ['patterns', LFREF%d, LFREF%d] )\n" % (last_refpat, fact_pat, last_refpat-1)
                fact_pat = last_refpat

            # negative option?
            if (mtex.maptoneg & 16):
                factt_pat, facmm_pat = facm_pat, fact_pat
            else:
                factt_pat, facmm_pat = fact_pat, facm_pat

            if mtex.blendtype==0:   # Mix
                # factt * def_var
                numpat += 1
                last_refpat += 1
                t = mtex.def_var
                st += "LFREF%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_refpat, t, t, t)
                numpat += 1
                last_refpat += 1
                st += "LFREF%d = s.newPattern('mul', ['patterns', LFREF%d, LFREF%d] )\n" % (last_refpat, factt_pat, last_refpat-1)
                # facmm * matref
                numpat += 1
                last_refpat += 1
                st += "LFREF%d = s.newPattern('mul', ['patterns', LFREF%d, LFREF%d] )\n" % (last_refpat, facmm_pat, matref)
                # fact*def_var + facm*matref
                numpat += 1
                last_refpat += 1
                st += "LFREF%d = s.newPattern('add', ['patterns', LFREF%d, LFREF%d] )\n" % (last_refpat, last_refpat-2, last_refpat-1)
            elif mtex.blendtype==1: # Mul
                # facmul+factt
                numpat += 1
                last_refpat += 1
                st += "LFREF%d = s.newPattern('add', ['patterns', LFREF%d, LFREF%d] )\n" % (last_refpat, facmul_pat, factt_pat)
                # prev. * matref
                numpat += 1
                last_refpat += 1
                st += "LFREF%d = s.newPattern('mul', ['patterns', LFREF%d, LFREF%d] )\n" % (last_refpat, last_refpat-1, matref)
            else:   # Add/Sub
                # factt + matref, always as add, factt negated above
                numpat += 1
                last_refpat += 1
                st += "LFREF%d = s.newPattern('add', ['patterns', LFREF%d, LFREF%d] )\n" % (last_refpat, matref, factt_pat)

            st += "\n"

            ref_used = 1

        if (mtex.mapto & 32) or (mtex.maptoneg & 32):   # Spec, does use maptoneg
            # intensity used as specular value mapping

            # matspec is only material spec when first time use of specchan., otherwise it is last specpat
            if not spec_used:
                numpat += 1
                last_specpat += 1
                st += "LFSPEC%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_specpat, mt.spec, mt.spec, mt.spec)
            else:
                last_specpat += 1
                st += "LFSPEC%d = LFSPEC%d\n" % (last_specpat, last_specpat-1)
            matspec = last_specpat

            # last intensity texture
            last_specpat += 1
            st += "LFSPEC%d = LFTEX%d\n" % (last_specpat, last_intenstex)

            # fact
            numpat += 1
            last_specpat += 1
            fact_pat = last_specpat
            t = mtex.varfac
            st += "LFSPEC%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_specpat, t, t, t)
            # *Tin, which is intensity, texture is already intensity, so multiply with texture
            numpat += 1
            last_specpat += 1
            fact_pat = last_specpat
            st += "LFSPEC%d = s.newPattern('mul', ['patterns', LFSPEC%d, LFSPEC%d] )\n" % (last_specpat, last_specpat-2, last_specpat-1)

            # facm, as 'not' of fact
            numpat += 1
            last_specpat += 1
            facm_pat = last_specpat
            st += "LFSPEC%d = s.newPattern('not', ['pattern', LFSPEC%d] )\n" % (last_specpat, fact_pat)

            if mtex.blendtype==1:
                # for 'Mul', facmul = 1-varfac
                numpat += 1
                last_specpat += 1
                t = 1.0-mtex.varfac
                st += "LFSPEC%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_specpat, t, t, t)
                facmul_pat = last_specpat

            if mtex.blendtype==3:
                # for 'Sub', fact = -fact, has to be done here, can't use 'sub' pat below
                numpat += 1
                last_specpat += 1
                st += "LFSPEC%d = s.newPattern('tint', ['color', vector3(-1.0, -1.0, -1.0)] )\n" % last_specpat
                numpat += 1
                last_specpat += 1
                st += "LFSPEC%d = s.newPattern('mul', ['patterns', LFSPEC%d, LFSPEC%d] )\n" % (last_specpat, fact_pat, last_specpat-1)
                fact_pat = last_specpat

            # negative option?
            if (mtex.maptoneg & 32):
                factt_pat, facmm_pat = facm_pat, fact_pat
            else:
                factt_pat, facmm_pat = fact_pat, facm_pat

            if mtex.blendtype==0:   # Mix
                # factt * def_var
                numpat += 1
                last_specpat += 1
                t = mtex.def_var
                st += "LFSPEC%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_specpat, t, t, t)
                numpat += 1
                last_specpat += 1
                st += "LFSPEC%d = s.newPattern('mul', ['patterns', LFSPEC%d, LFSPEC%d] )\n" % (last_specpat, factt_pat, last_specpat-1)
                # facmm * matspec
                numpat += 1
                last_specpat += 1
                st += "LFSPEC%d = s.newPattern('mul', ['patterns', LFSPEC%d, LFSPEC%d] )\n" % (last_specpat, facmm_pat, matspec)
                # fact*def_var + facm*matspec
                numpat += 1
                last_specpat += 1
                st += "LFSPEC%d = s.newPattern('add', ['patterns', LFSPEC%d, LFSPEC%d] )\n" % (last_specpat, last_specpat-2, last_specpat-1)
            elif mtex.blendtype==1: # Mul
                # facmul+factt
                numpat += 1
                last_specpat += 1
                st += "LFSPEC%d = s.newPattern('add', ['patterns', LFSPEC%d, LFSPEC%d] )\n" % (last_specpat, facmul_pat, factt_pat)
                # prev. * matspec
                numpat += 1
                last_specpat += 1
                st += "LFSPEC%d = s.newPattern('mul', ['patterns', LFSPEC%d, LFSPEC%d] )\n" % (last_specpat, last_specpat-1, matspec)
            else:   # Add/Sub
                # factt + matspec, always as add, factt negated above
                numpat += 1
                last_specpat += 1
                st += "LFSPEC%d = s.newPattern('add', ['patterns', LFSPEC%d, LFSPEC%d] )\n" % (last_specpat, matspec, factt_pat)

            st += "\n"

            spec_used = 1

        if (mtex.mapto & 64) or (mtex.maptoneg & 64):   # Emit, does use maptoneg
            # intensity used as emit value

            # matemit is only material emit when first time use of emitchan., otherwise it is last emitpat
            if not emit_used:
                numpat += 1
                last_emitpat += 1
                st += "LFEMIT%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_emitpat, mt.emit, mt.emit, mt.emit)
            else:
                last_emitpat += 1
                st += "LFEMIT%d = LFEMIT%d\n" % (last_emitpat, last_emitpat-1)
            matemit = last_emitpat

            # last intensity texture
            last_emitpat += 1
            st += "LFEMIT%d = LFTEX%d\n" % (last_emitpat, last_intenstex)

            # fact
            numpat += 1
            last_emitpat += 1
            fact_pat = last_emitpat
            t = mtex.varfac
            st += "LFEMIT%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_emitpat, t, t, t)
            # *Tin, which is intensity, texture is already intensity, so multiply with texture
            numpat += 1
            last_emitpat += 1
            fact_pat = last_emitpat
            st += "LFEMIT%d = s.newPattern('mul', ['patterns', LFEMIT%d, LFEMIT%d] )\n" % (last_emitpat, last_emitpat-2, last_emitpat-1)

            # facm, as 'not' of fact
            numpat += 1
            last_emitpat += 1
            facm_pat = last_emitpat
            st += "LFEMIT%d = s.newPattern('not', ['pattern', LFEMIT%d] )\n" % (last_emitpat, fact_pat)

            if mtex.blendtype==1:
                # for 'Mul', facmul = 1-varfac
                numpat += 1
                last_emitpat += 1
                t = 1.0-mtex.varfac
                st += "LFEMIT%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_emitpat, t, t, t)
                facmul_pat = last_emitpat

            if mtex.blendtype==3:
                # for 'Sub', fact = -fact, has to be done here, can't use 'sub' pat below
                numpat += 1
                last_emitpat += 1
                st += "LFEMIT%d = s.newPattern('tint', ['color', vector3(-1.0, -1.0, -1.0)] )\n" % last_emitpat
                numpat += 1
                last_emitpat += 1
                st += "LFEMIT%d = s.newPattern('mul', ['patterns', LFEMIT%d, LFEMIT%d] )\n" % (last_emitpat, fact_pat, last_emitpat-1)
                fact_pat = last_emitpat

            # negative option?
            if (mtex.maptoneg & 64):
                factt_pat, facmm_pat = facm_pat, fact_pat
            else:
                factt_pat, facmm_pat = fact_pat, facm_pat

            if mtex.blendtype==0:   # Mix
                # factt * def_var
                numpat += 1
                last_emitpat += 1
                t = mtex.def_var
                st += "LFEMIT%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_emitpat, t, t, t)
                numpat += 1
                last_emitpat += 1
                st += "LFEMIT%d = s.newPattern('mul', ['patterns', LFEMIT%d, LFEMIT%d] )\n" % (last_emitpat, factt_pat, last_emitpat-1)
                # facmm * matemit
                numpat += 1
                last_emitpat += 1
                st += "LFEMIT%d = s.newPattern('mul', ['patterns', LFEMIT%d, LFEMIT%d] )\n" % (last_emitpat, facmm_pat, matemit)
                # fact*def_var + facm*matemit
                numpat += 1
                last_emitpat += 1
                st += "LFEMIT%d = s.newPattern('add', ['patterns', LFEMIT%d, LFEMIT%d] )\n" % (last_emitpat, last_emitpat-2, last_emitpat-1)
            elif mtex.blendtype==1: # Mul
                # facmul+factt
                numpat += 1
                last_emitpat += 1
                st += "LFEMIT%d = s.newPattern('add', ['patterns', LFEMIT%d, LFEMIT%d] )\n" % (last_emitpat, facmul_pat, factt_pat)
                # prev. * matemit
                numpat += 1
                last_emitpat += 1
                st += "LFEMIT%d = s.newPattern('mul', ['patterns', LFEMIT%d, LFEMIT%d] )\n" % (last_emitpat, last_emitpat-1, matemit)
            else:   # Add/Sub
                # factt + matemit, always as add, factt negated above
                numpat += 1
                last_emitpat += 1
                st += "LFEMIT%d = s.newPattern('add', ['patterns', LFEMIT%d, LFEMIT%d] )\n" % (last_emitpat, matemit, factt_pat)

            st += "\n"

            emit_used = 1

        if (mtex.mapto & 128) or (mtex.maptoneg & 128):     # Alpha, does use maptoneg
            # intensity used as alpha value
            # DOES NOT WORK AS IT SHOULD, CAN'T REALLY BE DONE,
            # NO ALPHA IN LF, FAKED USING REFRACTION COLOR WITH IOR 1.0

            # matalpha is only material alpha when first time use of alphachan., otherwise it is last alphapat
            if not alpha_used:
                numpat += 1
                last_alphapat += 1
                st += "LFALPHA%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_alphapat, mt.alpha, mt.alpha, mt.alpha)
            else:
                last_alphapat += 1
                st += "LFALPHA%d = LFALPHA%d\n" % (last_alphapat, last_alphapat-1)
            matalpha = last_alphapat

            # last intensity texture
            last_alphapat += 1
            st += "LFALPHA%d = LFTEX%d\n" % (last_alphapat, last_intenstex)

            # fact
            numpat += 1
            last_alphapat += 1
            fact_pat = last_alphapat
            t = mtex.varfac
            st += "LFALPHA%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_alphapat, t, t, t)
            # *Tin, which is intensity, texture is already intensity, so multiply with texture
            numpat += 1
            last_alphapat += 1
            fact_pat = last_alphapat
            st += "LFALPHA%d = s.newPattern('mul', ['patterns', LFALPHA%d, LFALPHA%d] )\n" % (last_alphapat, last_alphapat-2, last_alphapat-1)

            # facm, as 'not' of fact
            numpat += 1
            last_alphapat += 1
            facm_pat = last_alphapat
            st += "LFALPHA%d = s.newPattern('not', ['pattern', LFALPHA%d] )\n" % (last_alphapat, fact_pat)

            if mtex.blendtype==1:
                # for 'Mul', facmul = 1-varfac
                numpat += 1
                last_alphapat += 1
                t = 1.0-mtex.varfac
                st += "LFALPHA%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_alphapat, t, t, t)
                facmul_pat = last_alphapat

            if mtex.blendtype==3:
                # for 'Sub', fact = -fact, has to be done here, can't use 'sub' pat below
                numpat += 1
                last_alphapat += 1
                st += "LFALPHA%d = s.newPattern('tint', ['color', vector3(-1.0, -1.0, -1.0)] )\n" % last_alphapat
                numpat += 1
                last_alphapat += 1
                st += "LFALPHA%d = s.newPattern('mul', ['patterns', LFALPHA%d, LFALPHA%d] )\n" % (last_alphapat, fact_pat, last_alphapat-1)
                fact_pat = last_alphapat

            # negative option?
            if (mtex.maptoneg & 128):
                factt_pat, facmm_pat = facm_pat, fact_pat
            else:
                factt_pat, facmm_pat = fact_pat, facm_pat

            if mtex.blendtype==0:   # Mix
                # factt * def_var
                numpat += 1
                last_alphapat += 1
                t = mtex.def_var
                st += "LFALPHA%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_alphapat, t, t, t)
                numpat += 1
                last_alphapat += 1
                st += "LFALPHA%d = s.newPattern('mul', ['patterns', LFALPHA%d, LFALPHA%d] )\n" % (last_alphapat, factt_pat, last_alphapat-1)
                # facmm * matalpha
                numpat += 1
                last_alphapat += 1
                st += "LFALPHA%d = s.newPattern('mul', ['patterns', LFALPHA%d, LFALPHA%d] )\n" % (last_alphapat, facmm_pat, matalpha)
                # fact*def_var + facm*matalpha
                numpat += 1
                last_alphapat += 1
                st += "LFALPHA%d = s.newPattern('add', ['patterns', LFALPHA%d, LFALPHA%d] )\n" % (last_alphapat, last_alphapat-2, last_alphapat-1)
            elif mtex.blendtype==1: # Mul
                # facmul+factt
                numpat += 1
                last_alphapat += 1
                st += "LFALPHA%d = s.newPattern('add', ['patterns', LFALPHA%d, LFALPHA%d] )\n" % (last_alphapat, facmul_pat, factt_pat)
                # prev. * matalpha
                numpat += 1
                last_alphapat += 1
                st += "LFALPHA%d = s.newPattern('mul', ['patterns', LFALPHA%d, LFALPHA%d] )\n" % (last_alphapat, last_alphapat-1, matalpha)
            else:   # Add/Sub
                # factt + matalpha, always as add, factt negated above
                numpat += 1
                last_alphapat += 1
                st += "LFALPHA%d = s.newPattern('add', ['patterns', LFALPHA%d, LFALPHA%d] )\n" % (last_alphapat, matalpha, factt_pat)

            st += "\n"

            alpha_used = 1

        if (mtex.mapto & 256) or (mtex.maptoneg & 256): # Hard, does use maptoneg
            # intensity used as specular hard value

            # DOES NOT WORK IN LF, ANOTHER BUG?
            # ANY OTHER PATTERN BUT THE ACTUAL IMAGE ITSELF, WILL PRODUCE NO RESULT...
            # FOR THIS REASON EVERYTHING IS SKIPPED AND THE TEXTURE ALWAYS USED DIRECTLY
            # USING COMPOSE AS 'Nor'

            hardpat_chain.append(last_intenstex)

            """
            # mathard is only material hard when first time use of hardchan., otherwise it is last hardpat
            if not hard_used:
                numpat += 1
                last_hardpat += 1
                t = mt.har ** -0.7071068
                st += "LFHARD%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_hardpat, t, t, t)
            else:
                last_hardpat += 1
                st += "LFHARD%d = LFHARD%d\n" % (last_hardpat, last_hardpat-1)
            mathard = last_hardpat

            # last intensity texture
            last_hardpat += 1
            st += "LFHARD%d = LFTEX%d\n" % (last_hardpat, last_intenstex)

            # fact
            numpat += 1
            last_hardpat += 1
            fact_pat = last_hardpat
            t = mtex.varfac
            st += "LFHARD%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_hardpat, t, t, t)
            # *Tin, which is intensity, texture is already intensity, so multiply with texture
            numpat += 1
            last_hardpat += 1
            fact_pat = last_hardpat
            st += "LFHARD%d = s.newPattern('mul', ['patterns', LFHARD%d, LFHARD%d] )\n" % (last_hardpat, last_hardpat-2, last_hardpat-1)

            # facm, as 'not' of fact
            numpat += 1
            last_hardpat += 1
            facm_pat = last_hardpat
            st += "LFHARD%d = s.newPattern('not', ['pattern', LFHARD%d] )\n" % (last_hardpat, fact_pat)

            if mtex.blendtype==1:
                # for 'Mul', facmul = 1-varfac
                numpat += 1
                last_hardpat += 1
                t = 1.0-mtex.varfac
                st += "LFHARD%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_hardpat, t, t, t)
                facmul_pat = last_hardpat

            if mtex.blendtype==3:
                # for 'Sub', fact = -fact, has to be done here, can't use 'sub' pat below
                numpat += 1
                last_hardpat += 1
                st += "LFHARD%d = s.newPattern('tint', ['color', vector3(-1.0, -1.0, -1.0)] )\n" % last_hardpat
                numpat += 1
                last_hardpat += 1
                st += "LFHARD%d = s.newPattern('mul', ['patterns', LFHARD%d, LFHARD%d] )\n" % (last_hardpat, fact_pat, last_hardpat-1)
                fact_pat = last_hardpat

            # negative option?
            if (mtex.maptoneg & 256):
                factt_pat, facmm_pat = facm_pat, fact_pat
            else:
                factt_pat, facmm_pat = fact_pat, facm_pat

            if mtex.blendtype==0:   # Mix
                # factt * def_var
                numpat += 1
                last_hardpat += 1
                t = mtex.def_var
                st += "LFHARD%d = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (last_hardpat, t, t, t)
                numpat += 1
                last_hardpat += 1
                st += "LFHARD%d = s.newPattern('mul', ['patterns', LFHARD%d, LFHARD%d] )\n" % (last_hardpat, factt_pat, last_hardpat-1)
                # facmm * mathard
                numpat += 1
                last_hardpat += 1
                st += "LFHARD%d = s.newPattern('mul', ['patterns', LFHARD%d, LFHARD%d] )\n" % (last_hardpat, facmm_pat, mathard)
                # fact*def_var + facm*mathard
                numpat += 1
                last_hardpat += 1
                st += "LFHARD%d = s.newPattern('add', ['patterns', LFHARD%d, LFHARD%d] )\n" % (last_hardpat, last_hardpat-2, last_hardpat-1)
            elif mtex.blendtype==1: # Mul
                # facmul+factt
                numpat += 1
                last_hardpat += 1
                st += "LFHARD%d = s.newPattern('add', ['patterns', LFHARD%d, LFHARD%d] )\n" % (last_hardpat, facmul_pat, factt_pat)
                # prev. * mathard
                numpat += 1
                last_hardpat += 1
                st += "LFHARD%d = s.newPattern('mul', ['patterns', LFHARD%d, LFHARD%d] )\n" % (last_hardpat, last_hardpat-1, mathard)
            else:   # Add/Sub
                # factt + mathard, always as add, factt negated above
                numpat += 1
                last_hardpat += 1
                st += "LFHARD%d = s.newPattern('add', ['patterns', LFHARD%d, LFHARD%d] )\n" % (last_hardpat, mathard, factt_pat)

            st += "\n"
            """

            hard_used = 1

    # compose the complete bump/displacement map pattern
    if nor_used:
        if len(norpat_chain)>1:
            numpat += 1
            st += "LFNOR%d = s.newPattern('compose', ['patterns'" % numpat
            for np in norpat_chain:
                st += ", LFTEX%d" % np
            st += "] )\n\n"
        else:
            # one norpat
            numpat += 1
            st += "LFNOR%d = LFTEX%d\n\n" % (numpat, norpat_chain[0])
        last_norpat = numpat

    # compose the complete hard map pattern, see above
    if hard_used:
        if len(hardpat_chain)>1:
            numpat += 1
            st += "LFHARD%d = s.newPattern('compose', ['patterns'" % numpat
            for np in norpat_chain:
                st += ", LFTEX%d" % np
            st += "] )\n\n"
        else:
            # one norpat
            numpat += 1
            st += "LFHARD%d = LFTEX%d\n\n" % (numpat, hardpat_chain[0])
        last_hardpat = numpat

    # combine all patterns into one

    # combine col and ref
    if col_used and ref_used:
        st += "LFDIF_KD = s.newPattern('mul', ['patterns', LFCOL%d, LFREF%d] )\n\n" % (last_colpat, last_refpat)
    elif col_used:
        st += "LFDIF_KD = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (mt.ref, mt.ref, mt.ref)
        st += "LFDIF_KD = s.newPattern('mul', ['patterns', LFDIF_KD, LFCOL%d] )\n\n" % last_colpat
    elif ref_used:
        st += "LFDIF_KD = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (mt.r, mt.g, mt.b)
        st += "LFDIF_KD = s.newPattern('mul', ['patterns', LFDIF_KD, LFREF%d] )\n\n" % last_refpat

    # combine specular color and value if both used together
    if csp_used and spec_used:
        st += "LFSPEC_KS = s.newPattern('mul', ['patterns', LFCSP%d, LFSPEC%d] )\n\n" % (last_csppat, last_specpat)
    elif spec_used:
        # spec value only
        st += "LFSPEC_KS = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (mt.specr, mt.specg, mt.specb)
        st += "LFSPEC_KS = s.newPattern('mul', ['patterns', LFSPEC%d, LFSPEC_KS] )\n\n" % last_specpat
    elif csp_used:
        st += "LFSPEC_KS = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (mt.spec, mt.spec, mt.spec)
        st += "LFSPEC_KS = s.newPattern('mul', ['patterns', LFCSP%d, LFSPEC_KS] )\n\n" % last_csppat

    # combine cmir and emit
    if cmr_used and emit_used:
        st += "LFAMB_KA1 = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (mt.r, mt.g, mt.b)
        st += "LFAMB_KA1 = s.newPattern('mul', ['patterns', LFEMIT%d, LFAMB_KA1] )\n" % last_emitpat
        st += "LFAMB_KA2 = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (mt.mirr, mt.mirg, mt.mirb)
        st += "LFAMB_KA2 = s.newPattern('mul', ['patterns', LFCMR%d, LFAMB_KA2] )\n" % last_cmrpat
        st += "LFAMB_KA = s.newPattern('add', ['patterns', LFAMB_KA1, LFAMB_KA2] )\n\n"
    elif emit_used:
        st += "LFAMB_KA = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (mt.r, mt.g, mt.b)
        st += "LFAMB_KA = s.newPattern('mul', ['patterns', LFEMIT%d, LFAMB_KA] )\n\n" % last_emitpat
    elif cmr_used:
        st += "LFAMB_KA = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (mt.mirr, mt.mirg, mt.mirb)
        st += "LFAMB_KA = s.newPattern('mul', ['patterns', LFCMR%d, LFAMB_KA] )\n\n" % last_cmrpat

    if alpha_used and (mt.mode & 64):
        last_alphapat += 1
        st += "LFALPHA%d = s.newPattern('not', ['pattern', LFALPHA%d] )\n" %(last_alphapat, last_alphapat-1)
        if not col_used:
            st += "LFCOL0 = s.newPattern('tint', ['color', vector3(%f, %f, %f)] )\n" % (mt.r*mt.ref, mt.g*mt.ref, mt.b*mt.ref)
        st += "LFALPHACOL_T = s.newPattern('mul', ['patterns', LFCOL%d, LFALPHA%d] )\n\n" % (last_colpat, last_alphapat)

    # now combine everything into the actual material
    st += "%s = s.newMaterial( 'generic', [\n" % dupmatname

    # ALL PATTERNS MUST BE COMBINED IN SINGLE PATTERN IF MULTIPLE USE (REF*COL,ETC..)
    # ALSO, MIGHT REVISE ALL MODULATIONS AS kX = COLOR=1, kX = MODULATOR, IT SEEMS TO BE MORE LIKE A MIX ALGO. THEN A MULTIPLY
    if alpha_used and (mt.mode & 64):
        st += "\t\t 'kdr', vector3(0.0, 0.0, 0.0),\n"
    elif col_used or ref_used:
        # ref modulator
        st += "\t\t 'kdr', vector3(1.0, 1.0, 1.0),\n"
        st += "\t\t 'kdr', LFDIF_KD,\n"
    else:
        st += "\t\t 'kdr', vector3(%f, %f, %f),\n" % (mt.r*mt.ref, mt.g*mt.ref, mt.b*mt.ref)

    if cmr_used or emit_used:
        st += "\t\t 'ka', vector3(1.0, 1.0, 1.0),\n"
        st += "\t\t 'ka', LFAMB_KA,\n"
    else:
        st += "\t\t 'ka', vector3(%f, %f, %f),\n" % (mt.r*mt.emit, mt.g*mt.emit, mt.b*mt.emit)

    # SpTra value to enhance specular shinyness
    st += "\t\t 'shinyness', %f,\n" % mt.spectra

    # displacement
    if nor_used: st += "\t\t 'displacement', LFNOR%d,\n" % last_norpat

    # specular color/amount
    if csp_used or spec_used:
        # combination of specular color and specular value (LFCSP & LFSPEC)
        st += "\t\t 'ksr', vector3(1.0, 1.0, 1.0),\n"
        st += "\t\t 'ksr', LFSPEC_KS,\n"
    else:
        st += "\t\t 'ksr', vector3(%f, %f, %f),\n" % (mt.specr*mt.spec, mt.specg*mt.spec, mt.specb*mt.spec)

    # fake alpha mapping, as material with IOR of 1.0 (default), inverse alpha used to modulate refraction color
    # actual alpha used above to modulate diffuse color
    # ZTransp must be enabled
    if alpha_used and (mt.mode & 64):
        st += "\t\t 'kt', vector3(1.0, 1.0, 1.0),\n"
        st += "\t\t 'kt', LFALPHACOL_T,\n"

    # specular roughness, ksg default is close enough to Blender
    st += "\t\t 'km', %f" % (mt.har ** -0.7071068)
    if hard_used: st += ",\n\t\t 'km', LFHARD%d" % last_hardpat

    if Tglit_toggle.val: st += ",\n\t\t 'glitter', 1"

    # switch on transmission if ZTransp enabled
    if (mt.mode & 64) and not caustics: st += ",\n\t\t 'transmission', 1"

    # disable shadows when 'traceable' switched off
    if ((mt.mode & 1)==0): st += ",\n\t\t 'shadowing', 0.0"

    st += "\n\t ] )\n\n"

    st += "### END BLENDFILE MATERIAL: %s\n\n\n" % dupmatname

    matfile.write(st)


#######################################################################################################################################


# Writes default material when no material specified for object
def WRITE_DEFAULTMAT(radiosity):
    global matnames
    # is this material already written? if so, don't duplicate
    bdef_name = 'BLENDER_DEFAULT'
    if bdef_name not in matnames:
        # no, it isn't, save the name
        print "Writing default blender material %s" % bdef_name
        matnames.append(bdef_name)
        st = "### BLENDER DEFAULT MATERIAL\n"
        st += "%s = s.newMaterial( 'standard', [ 'kc', vector3(0.8, 0.8, 0.8), 'kd', 0.8, 'km', 0.062899441" % bdef_name
        if radiosity: st += " ,'radiosity', 1"
        st += " ] )\n\n\n"
        matfile.write(st)


##########################################

#########################
# MAIN PART STARTS HERE #
#########################

# Find the full path of the first texture in the mesh
def GetTexturePath(mesh):
    # Since the image name does not contain the full path and can actually be only a part of
    # the actual name, find the actual file matching the namefragment including the full path.
    if not mesh.hasFaceUV(): return # no uv-coords, no texture(s)
    texname = None
    for f in mesh.faces:
        if f.image:
            texname = f.image.name
            break
    if texname==None:
        print "Mesh has UV coords, but no textures found!"
        return
    # Split of any blender appended numbers like .001, leaving only the real texture name
    texname = texname.split('.')
    # recombine with the extension, ignore all extras
    if len(texname)>1:
        texname = texname[0] + '.' + texname[1]
    else:
        texname = texname[0]
    if texname:
        # find the full path to the texture matching the name, including subdirectories
        results_matched = WalkFind(TEXROOT, 1, texname)
        if results_matched:
            # if there are more matches, use the one which has .tga as extension
            if len(results_matched)>1:
                tganame = None
                for r in results_matched:
                    if r.lower().find('.tga')!=-1:
                        tganame = r
                        break
            else:
                # otherwise use the first in the list, will be converted if possible and not a .tga
                tganame = results_matched[0]
            return tganame
    return


def TEXTURE_CONVERT(texpath, conv2gray=0):
    if TOTGA_OK:
        GetOutdir()
        # split of filename
        fname = os.path.split(texpath)[1]
        fname = fname.split('.', 1)[0] + '.tga'     # replace extension with .tga
        # if grayscale conversion, put 'BW_' in front of texturename
        if conv2gray:
            fname = 'BW_'+fname
            newtexpath = os.path.join(tgatex_dir, fname)
        else:
            newtexpath = os.path.join(tgatex_dir, fname)
        # Only convert if it does not exist yet
        if os.path.exists(newtexpath):
            # Already converted, nothing to be done
            print "Texture already converted, nothing done"
            ok = [1, '']
        else:
            ok = totga.ConvertLong(texpath, newtexpath, 0, conv2gray)   # no RLE compression, sometimes generates errors, might crash LF
        if not ok[0]:
            # Texture could not be converted.
            # This means it was either already a tga in which case it is ok (uses actual path instead, unless it has spaces),
            # or there really was an error, print message in any case
            print ok[1]
            # Since the LF ascii format doesn't accept spaces in filenames/paths,
            # when a path has spaces, copy it anyway to the texture directory,
            # otherwise LFArender will fail.
            # A bit clumsy this, but works...
            if ok[1].find('already targa')!=-1 and texpath.find(' ')!=-1:
                print "Input filename contains spaces, copying to destination"
                # copy without shutil
                try:
                    
                    fp1 = open(texpath, 'rb')
                    fp2 = open(newtexpath, 'wb')
                    fp2.write(fp1.read())
                    fp2.close()
                    fp1.close()
                

                except:
                    print "Error, while copying!"
                else:
                    texpath = newtexpath
        else:
            # texture was converted, return the new texture path
            texpath = newtexpath
    else:
        print "Texture conversion module not available, no conversion done!"
    return texpath


##########################################################################################
# BLENDER METABALL/NURB/BSPLINE TO LIGHTFLOW
##########################################################################################

def EXPORT_LF_METABALL(mbob, MAIN_MBALL):
    # Create Lightflow metaball data, all metaball groups share the material of
    # the main metaball as specified.
    firstmb = MAIN_MBALL.data
    print "MetaBall ", firstmb
    st = "### BLENDFILE METABALL %s\n\n" % mbob.id.name[2:] # without id

    # Use direct object matrix instead of blendfile matrix to allow animation
    # not that this does not work of course for individual element animations, only the entire group
    bmtx = Blender.Object.Get(mbob.id.name[2:]).matrix
    st += "s.transformBegin(transform().setMatrix_rm( " + BMTX_TO_STRING(bmtx) + " ))\n\n"

    # if material used, only use first material in the list of the main metaball
    if ('mat' in dir(firstmb)) and len(firstmb.mat):
        st += "s.materialBegin(%s)\n" % firstmb.mat[0].id.name[2:]
    else:
        st += "s.materialBegin(BLENDER_DEFAULT)\n"

    # the actual metaballs (meta-elements)
    st += "s.addObject( s.newObject('blob', [\n"
    st += "\t\t 'threshold', %f" % firstmb.thresh
    mb = mbob.data
    mel = mb.elems.first
    while mel:
        # 0.5*stiffness used as strength value
        st += ",\n\t\t 'blob', vector3(%f, %f, %f), %f, %f" % (mel.x, mel.y, mel.z, mel.rad, 0.5*mel.s)
        mel = mel.next
    st += '\n'
    st += "] ) )\n"
    st += "s.materialEnd()\n\n" 

    st += "s.transformEnd()\n\n"
        
    st += "### END BLENDFILE METABALL %s\n\n" % mbob.id.name[2:]
    file.write(st)


# address sort comparison function for NURBS/BSPLINE
def adr_cpm(a, b):
    x = '0x'+a.address[2:]
    y = '0x'+b.address[2:]
    exec('t = %s-%s' % (x,y))
    return t


# EXPORT NURBS, NOT USED AT THE MOMENT, DEGREES IS WRONG, VECTORS TOO PROBABLY (4-DIM OR 3-DIM?)
def EXPORT_LF_NURB(nbob):
    # Create Lightflow nurb object (if possible)

    curve = nbob.data
    st = "### BLENDFILE CURVE/NURB/SURFACE %s\n\n" % nbob.id.name[2:]   # without id

    nb = curve.nurb.first

    # create code for points and knots array data
    # points first
    st += "NURBS_POINTS = vector4array()\n"
    st += "NURBS_POINTS.setSize(%d)\n" % len(nb.bp)
    # sort by address first to put things in order (I hope)
    nb.bp.sort(adr_cpm)
    st += "PLIST = ["
    i = 0
    for bp in nb.bp:
        st += "vector4(%f, %f, %f, %f)," % tuple(bp.vec)
        i += 1
        if ((i & 3)==0) and (i!=len(nb.bp)): st += "\n"
    st = st[:-1]    # remove last comma
    st += "]\n"
    st += "for i in range(len(PLIST)):\n"
    st += "\tNURBS_POINTS.set(i, PLIST[i])\n\n"

    # Then knots
    # uknots
    st += "NURBS_KNOTSU = floatarray()\n"
    st += "NURBS_KNOTSU.setSize(%d)\n" % len(nb.knotsu)
    st += "KLIST1 = ["
    i = 0
    for k in nb.knotsu:
        st += "%f," % k
        i += 1
        if ((i & 7)==0) and (i!=len(nb.knotsu)): st += "\n"
    st = st[:-1]    # remove last comma
    st += "]\n"
    st += "for i in range(len(KLIST1)):\n"
    st += "\tNURBS_KNOTSU.set(i, KLIST1[i])\n\n"

    # vknots
    st += "NURBS_KNOTSV = floatarray()\n"
    st += "NURBS_KNOTSV.setSize(%d)\n" % len(nb.knotsv)
    st += "KLIST2 = ["
    i = 0
    for k in nb.knotsv:
        st += "%f," % k
        i += 1
        if ((i & 7)==0) and (i!=len(nb.knotsv)): st += "\n"
    st = st[:-1]    # remove last comma
    st += "]\n"
    st += "for i in range(len(KLIST2)):\n"
    st += "\tNURBS_KNOTSV.set(i, KLIST2[i])\n\n"

    # transform, use direct object matrix instead of blendfile matrix to allow animation
    bmtx = Blender.Object.Get(nbob.id.name[2:]).matrix
    st += "s.transformBegin(transform().setMatrix_rm( " + BMTX_TO_STRING(bmtx) + " ))\n\n"

    # if material used, only use first material in the list
    if ('mat' in dir(curve)) and len(curve.mat):
        st += "s.materialBegin(%s)\n" % curve.mat[0].id.name[2:]
    else:
        st += "s.materialBegin(BLENDER_DEFAULT)\n"

    st += "s.addObject( s.newObject('nurbs', [\n"
    st += "\t 'size', %d, %d,\n" % (nb.pntsu, nb.pntsv)
    t1 = len(nb.knotsu) - nb.pntsu - 1
    t2 = len(nb.knotsv) - nb.pntsv - 1
    st += "\t 'degree', %d, %d,\n" % (t1, t2)
    # point data
    st += "\t 'points', NURBS_POINTS,\n"
    # knots
    st += "\t 'knots', NURBS_KNOTSU, NURBS_KNOTSV,\n"
    # tolerance, curvature (defaults)
    st += "\t 'tolerance', 0.5, 0.1, 0.0,\n"
    st += "\t 'curvature', 0.01\n"
    st += "] ) )\n"

    st += "s.materialEnd()\n\n"

    st += "s.transformEnd()\n\n"
    st += "### END BLENDFILE CURVE/NURB/SURFACE %s\n\n" % nbob.id.name[2:]
    file.write(st)


def EXPORT_LF_BSPLINE(nbob):
    # Create Lightflow bspline object (if possible)

    curve = nbob.data
    st = "### BLENDFILE CURVE/NURB/SURFACE AS BSPLINE %s\n\n" % nbob.id.name[2:]    # without id

    nb = curve.nurb.first

    # create code for points and knots array data
    # points first
    st += "BPOINTS = vector3array()\n"
    st += "BPOINTS.setSize(%d)\n" % len(nb.bp)
    # sort by address first to put things in order
    nb.bp.sort(adr_cpm)
    st += "PLIST = ["
    i = 0
    for bp in nb.bp:
        st += "vector3(%f, %f, %f)," % tuple(bp.vec[:3])
        i += 1
        if ((i & 3)==0) and (i!=len(nb.bp)): st += "\n"
    st = st[:-1]    # remove last comma
    st += "]\n"
    st += "for i in range(len(PLIST)):\n"
    st += "\tBPOINTS.set(i, PLIST[i])\n\n"

    # transform
    # Use direct Blender object matrix instead of blendfile matrix to allow animation
    bmtx = Blender.Object.Get(nbob.id.name[2:]).matrix
    st += "s.transformBegin(transform().setMatrix_rm( " + BMTX_TO_STRING(bmtx) + " ))\n\n"

    # if material used, only use first material in the list
    if ('mat' in dir(curve)) and len(curve.mat):
        st += "s.materialBegin(%s)\n" % curve.mat[0].id.name[2:]
    else:
        st += "s.materialBegin(BLENDER_DEFAULT)\n"

    st += "s.addObject( s.newObject('bspline', [\n"
    st += "\t 'size', %d, %d,\n" % (nb.pntsu, nb.pntsv)
    # point data
    st += "\t 'points', BPOINTS,\n"
    # step value & basis matrix
    if (nb.flagu & 2):      # EndpointUV, looks most like LF Bezier
        wrapu = "Bezier"
    elif (nb.flagu & 4):    # BezierUV, looks most like LF CatmullRom (!)
        wrapu = "CatmullRom"
    else:                   # UniformUV, LF BSpline, works best with Blender anysurf. when using the same weight on every CV
        wrapu = "BSpline"
    # basis matrix
    if (nb.flagv & 2):
        wrapv = "Bezier"
    elif (nb.flagv & 4):
        wrapv = "CatmullRom"
    else:
        wrapv = "BSpline"
    st += "\t 'step', %sStep(), %sStep(),\n" % (wrapu, wrapv)
    st += "\t 'basis', %sBasis(), %sBasis(),\n" % (wrapu, wrapv)
    # wrap u, v (cyclic u/v)
    st += "\t 'wrap', %d, %d,\n" % (nb.flagu & 1, nb.flagv & 1)
    # tolerance, curvature (defaults)
    st += "\t 'tolerance', 0.02, 0.1, 0.05,\n" #0.5, 0.1, 0.0,\n"
    st += "\t 'curvature', 0.01\n"
    st += "] ) )\n"

    st += "del BPOINTS\n\n"

    st += "s.materialEnd()\n\n"

    st += "s.transformEnd()\n\n"
    st += "### END BLENDFILE BSPLINE %s\n\n" % nbob.id.name[2:]
    file.write(st)


##########################################################################################

# function which decides which material to write
def WRITE_MATERIAL(BFMOD, TEXSPACE, WORLD_COLOR, material_name, obname, texname, matnum, radiosity, caustics, texcontrol, camob):
    
    
 
    print "Writing material: %s" % material_name

    # used when blendfile import enabled, extension materials have priority over blendfile materials
    ALLMATIDS = ['_GLAS', '_DIGL', '_DIOG', '_METL', '_DIME', '_DIOM', '_AMBI', '_DISP', '_DISO', '_SPID']

    

    # the extension if specified
    mat_id = material_name[-5:]

    

    if BFREAD_OK and Tblendimp.val and (mat_id not in ALLMATIDS):   # USE MATERIALS FROM BLENDFILE
        bfmat = BFMOD.getMaterial(material_name)
        BLEND2LF(BFMOD, bfmat, obname, TEXSPACE, camob, caustics)
        return

    

    material = Blender.Material.Get(material_name)
    if mat_id=='_GLAS':     # GLASS PLUS UV-TEXTURE FOR COLORMAPPING, WHEN UV-TEXTURE IS USED
        WRITE_GLASS(material, texname, matnum, 1, 0, radiosity, caustics)

    elif mat_id=='_DIGL':   # GLASS PLUS UV-TEXTURE USED FOR COLOR AND DISPLACEMENT MAPPING
        WRITE_GLASS(material, texname, matnum, 1, 1, radiosity, caustics)

    elif mat_id=='_DIOG':   # GLASS PLUS UV-TEXTURE USED FOR DISPLACEMENT MAPPING ONLY
        WRITE_GLASS(material, texname, matnum, 0, 1, radiosity, caustics)

    elif mat_id=='_METL':   # METAL PLUS UV-TEXTURE FOR COLORMAPPING, WHEN UV-TEXTURE USED
        WRITE_METAL(material, texname, matnum, 1, 0, radiosity, caustics)

    elif mat_id=='_DIME':   # METAL PLUS UV-TEXTURE USED FOR COLOR MAPPING AND DISPLACEMENT MAPPING
        WRITE_METAL(material, texname, matnum, 1, 1, radiosity, caustics)

    elif mat_id=='_DIOM':   # METAL PLUS UV-TEXTURE USED FOR DISPLACEMENT MAPPING ONLY
        WRITE_METAL(material, texname, matnum, 0, 1, radiosity, caustics)

    elif mat_id=='_AMBI':   # AMBIENT (SHADELESS) MATERIAL, USEFUL WITH RADIOSIY TO EMULATE LIGHTING
        WRITE_AMBIENT(material, texname, matnum, WORLD_COLOR)

    elif mat_id=='_DISP':   # STANDARD MATERIAL WITH UV-TEXTURE USED FOR COLOR AND DISPLACEMENT MAPPING
        WRITE_STANDARD(material, texname, matnum, 1, 1, radiosity, caustics)

    elif mat_id=='_DISO':   # STANDARD MATERIAL WITH UV-TEXTURE USED FOR DISPLACEMENT MAPPING ONLY
        WRITE_STANDARD(material, texname, matnum, 0, 1, radiosity, caustics)

    elif mat_id=='_SPID':   # DIRECT MATSPIDER MATERIAL IMPORT
        # windows only, if on linux, same as standard material
        if sys.platform=='win32':
            WRITE_MATSPIDER(material, obname, texcontrol)
        else:
            print "MATSpider materials not supported on Linux, exported as standard material instead!"
            WRITE_STANDARD(material, texname, matnum, 1, 0, radiosity, caustics)
    else:   # NO ID, STANDARD MATERIAL, PLUS UV-TEXTURE FOR COLORMAPPING, WHEN UV-TEXTURE USED
        WRITE_STANDARD(material, texname, matnum, 1, 0, radiosity, caustics)


##########################################################################################

###############################
# THE big main export routine #
###############################

def ExportIt(selectedList=None):
    global texnames, matnames, file, anim_indent, matfile, MESH_PT_DICT, MATSPIDER_USECOUNT
    global BLENDFILE_USECOUNT, TEX_BOUNDS, BLENDFILE_LFIMG_LIST

    

    # get all used vars from buttons
    savestuff, radiosity, caustics = Tsavestuff.val, Tradiosity.val, Tcaustics.val

    

    WORLD_LIGHT, WORLD_TEX, WORLD_SIZE = TWORLD_LIGHT.val, TWORLD_TEX.val, TWORLD_SIZE.val

    

    WORLD_COLOR = [TWORLD_COLOR_R.val, TWORLD_COLOR_G.val, TWORLD_COLOR_B.val]

    

    trace_depth, radio_depth = Ttrace_depth.val, Tradio_depth.val

    radiosity_samples = Tradio_samples.val
    photon_count = Tphoton_count.val
    pcluster_d, pcluster_c = Tpcluster_d.val, Tpcluster_c.val

    # In case WORLD_TEX is "None", really make it None, ignore case
    if WORLD_TEX.lower() == "none": WORLD_TEX = None
        
    ######################################
    #  CREATING DIRECTORY'S FOR OUTPUT   #
    ######################################
    

    GetOutdir()

    

    # but NOT every frame when this is a render-from-blender animation, only create and write on first frame
    if Tanimation.val==1 and FirstFrame():
        WriteDirsSettings()
    else:
        WriteDirsSettings()

    #############################

    # A GLOBAL DICTIONARY OF USED TEXTURES TO MAKE SURE NO DUPLICATE PATTERNS ARE WRITTEN, OTHERWISE LIGHTLFOW CRASHES ON EXIT
    texnames = {}

    # AND SIMILAR FOR MATERIALS, BUT A LIST INSTEAD OF A DICTIONARY SINCE ONLY NAMES ARE USED FOR CHECKING
    matnames = []

    #############################

    # OPEN FILE FOR RESULT .PY
    file = open(pyfilepath, 'w')

    

    meshlist = []
    lamplist = []
    arealist = []
    meshnameslist = []  # list to keep track of used meshnames, alt-d linked meshes only need to be written once
    texture_control_list = []   # list used for texture control empties, used in conjuction with MATSpider materials
    # List to keep track of lamps which have "Halo' switched on
    # A cone primitive with an interior material will be added, this is generally rendered faster than full scene volumetrics
    # The list contains another list for every halolamp which contains the lamp name,
    # & rot,size,loc tuples for the necessary transform written later
    halocone_list = []

    # USE COUNT OF MATSPIDER MATERIALS WHICH CAN BE WRITTEN MULTIPLE TIMES BECAUSE OF TEXTURE TRANSFORM
    MATSPIDER_USECOUNT = {}

    # IDEM BLENDFILE MATERIALS
    BLENDFILE_USECOUNT = {}
    # AND LIST TO KEEP TRACK OF IMAGE TEXTURES IT WILL WRITE
    BLENDFILE_LFIMG_LIST = []

    
    try:
        # Check if there is a FOCUS empty
        FOCUS = Blender.Object.Get('FOCUS')

        

        # if there is, get it's location
        if FOCUS: FOCUS = list(FOCUS.loc)
    except:
        print 'no FOCUS'

        FOCUS=0
 
    print("Getting List of Meshes and lamps")

    # Re-get mesh data when 'Always Write' selected, otherwise only use object data (materials, transform)
    # Data is always loaded
    # ALSO RESET TEXTURE BOUNDS
    if Tautocheck.val==0:
        MESH_PT_DICT = {}
        TEX_BOUNDS = {}

    # only export objects from the specified layer(s)
    # FIND ALL OBJECTS TO EXPORT
    #for ob in Blender.Object.Get():
    for ob in Blender.Scene.GetCurrent().objects:
        if (Tlayer.val & ob.Layer):
            if BL_VERSION<=223:
                ISMESH = Blender210.isMesh(ob.name)
                ISLAMP = Blender210.isLamp(ob.name)
            else:
                tp = ob.getType()
                ISMESH = (tp=='Mesh')
                ISLAMP = (tp=='Lamp')
            if ISMESH:
                # mesh itself will also be exported if the material is _AMBI so the patch can be made visible
                if ob.name[-6:]=="PLIGHT":  # Now as everything in the script, extension at the END of the name
                    print("found arealight")
                    arealist.append(ob.name)
                # STORE THE MESH DATA POINTER IF NOT YET IN THE DICTIONARY, OTHERWISE GET IT FROM THE DICTIONARY
                # IF MESH IS IN THE 'SELECTED' LIST FOR ANIMATION EXPORT, DATA REQUEST IN ADDMESH() WILL ALWAYS HAPPEN ANYWAY
                if ob.name not in MESH_PT_DICT.keys():
                    if BL_VERSION<=223:
                        me = ob.data
                    else:
                        me = ob.getData()
                    MESH_PT_DICT[ob.name] = me
                else:
                    me = MESH_PT_DICT[ob.name]
                # reported by 'fullback': check if the mesh actually is there.
                # If vertices were deleted in editmode, the object is still identified as a mesh,
                # but the actual mesh is not there anymore.
                # To go even further, ignore meshes with less than 1 face and/or less than three vertices
                if (len(me.faces)<1) or (len(me.verts)<3):
                    print "Mesh with object name %s ignored, not enough faces and/or vertices" % me.name
                else:
                    meshlist.append(ob.name)
            elif ISLAMP:
                lamplist.append(ob.name)

    print "Got Meshes, arealights and lamps"
    if PRINT_TRACE: print "Current mesh data: ", MESH_PT_DICT.keys()

    ################################################################################
    # BLENDFILE IMPORT

    # BlendFile module
    BFMOD = None

    # metaball and 'nurbish' objects
    mball_list = []
    nurbs_list = []

    # IF BLENDFILE IMPORT IS ACTIVATED, GET EVERYTHING NEEDED FROM BLENDFILE HERE
    if BFREAD_OK and Tblendimp.val:
        print "Trying to import materials/metaballs/nurbs from blendfile..."
        # complete material keywords: 'MTex', 'Tex', 'Image', 'ColorBand'
        # complete Metaball keywords: 'MetaBall', 'MetaElem'
        # complete Nurb keywords:     'Curve', 'Nurb', 'BPoint', 'BezTriple'
        # needed for all: 'Object', 'Material'
        # Get metaballs & Nurbs
        mball_list = []
        nurb_list = []
        try:

            

            bfile = BFReader(Blender.Get('filename'))

            

            bfile.getData([ 'Object', 'Material',
                            'MTex', 'Tex', 'Image', 'ColorBand',
                            'MetaBall', 'MetaElem',
                            'Curve', 'Nurb', 'BPoint', 'BezTriple'])

            

            BFMOD = bfile.convert2Python()

            

            print "Number of total datablocks extracted from file:", len(BFMOD.Clist)

        except:
            raise Exception("Error in blendfile import")
        else:
            # get the MetaBalls and Curves
            mball_list = []
            nurbs_list = []
            # Search through object for metaballs and nurbs using the two letter identifier.
            # Can't use getMetaBall() or getNurb() here since the object is needed too.
            for ob in BFMOD.getObject():
                dt = ob.data
                if dt!=None:
                    if dt.id.name[:2]=='MB':    # metaball
                        mball_list.append(ob)
                    elif dt.id.name[:2]=='CU':  # Curve/Nurb
                        nurb_list.append(ob)
            print "Found %d metaballs." % len(mball_list)
            print "Found %d Nurbs/Curves/Surfaces" % len(nurb_list)

    ################################################################################
    

    # Get camera here, also needed in Blendfile export (cam matrix in Object mapping)
    if BL_VERSION>223:
        cameraObj = Blender.Scene.getCurrent().getCurrentCamera()
        # Camera might not be there, or maybe an object was temporarily set to the current camera
        if cameraObj==None:
            raise Exception("No active scene camera found, add a camera")
        tp = cameraObj.getType()
        if tp!='Camera':
            raise Exception("Camera object is a %s! Use alt-0 to reset the camera" % tp)
        camera = cameraObj.getData()
    else:
        cameraObj = Blender210.getCurrentScene().getCurrentCamera()
        # Camera might not be there, or maybe an object was temporarily set to the current camera
        if cameraObj==None:
            raise Exception("No active scene camera found, add a camera")
        if cameraObj.type!='Camera':
            raise Exception("Camera object is a %s! Use alt-0 to reset the camera" % cameraObj.type)
        camera = Blender210.getCamera(cameraObj.data)

    

    # MATERIAL CHECK
    # Since meshes which have more than one material when separated from the original mesh,
    # can still have the full set of materials of the mesh in it's material list,
    # it is necessary to find the materials that are actually used,
    # otherwise materials (unused but still exported) as well as the mesh (empty mesh, zero points) will be incorrectly exported.

    matrlist = []   # list of lists, containing the name(s) of all materials that are actually used
    midxlist = []   # list of lists, containing the actual indices of the materials that are actually used

    

    for mesh in meshlist:
        me = MESH_PT_DICT[mesh]
        if BL_VERSION>223:
            # must get from mesh in Publisher
            ob = Blender.Object.Get(mesh)
            me = ob.getData()
            memats = []

            

## jms : modif for 228
            if BL_VERSION<228:
                for mt in me.getMaterials():
                    memats.append(mt.name)
            else:
                
                for mt in me.materials:
                    memats.append(mt.name)
## jms : modif for 228

        else:
            # use data from dictionary, but get materials from Blender210 object
            # this way, there is no need to 'get' the meshdata again, and materials are still exported correctly when changed
            memats = Blender210.getObject(mesh).materials

        

        num_mats = len(memats)
        valid_matnames = []

        valid_matinds = []

        

        if len(memats)>1:
            for mt_idx in range(num_mats):
                if memats[mt_idx]!=None:
                    mat_ok = 0
                    # only need to find if the material is used at least once in the mesh
                    for f in me.faces:

                        if BL_VERSION<228:
                            mat_ok = (f.mat==mt_idx)
                        else:
                            mat_ok = (f.materialIndex==mt_idx)

                        if mat_ok: break

                    if mat_ok:
                        valid_matnames.append(memats[mt_idx])
                        valid_matinds.append(mt_idx)
        elif num_mats==1:
            # single material
            valid_matnames.append(memats[0])
            valid_matinds.append(0)
        else:
            # no material
            valid_matnames.append(None)
            valid_matinds.append(-1)
        matrlist.append(valid_matnames)
        midxlist.append(valid_matinds)

    

    # START WRITING THE .PY FILE
    file.write("from lightflowPM import *\n\n")

    

    # IF THIS IS A SINGLE ANIMATION SCRIPT, WRITE THE MAIN PART
    if Tanimation.val==2:
        WriteAnimScriptStart()
        anim_indent = '\t'
    else:
        anim_indent = ''

    

    file.write(anim_indent + ("s = scene()\n\n"))   # texmem not used anymore (LFArender)

    # set specular bounce depth
    if caustics:
        sp_depth = radio_depth
    else:
        sp_depth = 0

    # set diffuse bounce depth
    if radiosity:
        df_depth = radio_depth
    else:
        df_depth = 0

    

    if Tanimation.val==2:
        # SINGLE ANIMATION SCRIPT
        if savestuff==3:
            # WRITE CODE TO DETERMINE SAVE OR LOAD
            st = "\t# Determine if we need to save or load calculated data\n"
            st += "\tif curframe==0:\n"
            st += "\t\taction = 'save'\n"
            st += "\telse:\n"
            st += "\t\taction = 'load'\n\n"
            file.write(st)

    

    # THE RENDERING ENGINE, now always written
    st = anim_indent + "s.newInterface( 'default', [\n"
    st += "\t\t 'displacement', %d, 'shadows', %d, 'volumes', %d,\n" % (Tdisp_switch.val, Tshad_switch.val, Tvolm_switch.val)
    # number of processors
    st += "\t\t 'processors', %d,\n" % TCPU.val
    if Tcache_switch.val:
        st += "\t\t 'caching', %d, %d, %f, %f,\n" % (Tcache_size.val, Tcache_cells.val, Tcache_minrad.val, Tcache_maxrad.val)

    

    if Tanimation.val==2:
        # SINGLE ANIMATION SCRIPT, SAVE OR LOAD WHEN RADIOSITY IS USED
        if radiosity:
            if savestuff==3:
                st += "\t\t 'radiosity-file', 'DATA/%s.rad', action,\n" % outname
            elif savestuff==1:
                st += "\t\t 'radiosity-file', 'DATA/%s.rad', 'save',\n" % outname
            elif savestuff==2:
                st += "\t\t 'radiosity-file', 'DATA/%s.rad', 'load',\n" % outname
    elif savestuff==3:
        # only save when this is the first frame
        if FirstFrame():
            st += "\t\t 'radiosity-file', 'DATA/%s.rad', 'save',\n" % outname
        else:
            st += "\t\t 'radiosity-file', 'DATA/%s.rad', 'load',\n" % outname
    elif savestuff==1:
        st += "\t\t 'radiosity-file', 'DATA/%s.rad', 'save',\n" % outname
    elif savestuff==2:
        st += "\t\t 'radiosity-file', 'DATA/%s.rad', 'load',\n" % outname
    st += "\t\t 'trace-depth', %d,\n" % trace_depth
    st += "\t\t 'radiosity-depth', %d, %d,\n" % (df_depth, sp_depth)
    st += "\t\t 'radiosity-samples', %d,\n" % radiosity_samples
    st += "\t\t 'radiosity-threshold', %f,\n" % Trad_thold.val
    st += "\t\t 'radiosity-reuse-distance', %f, %f, %f,\n" % (Trusedist_scr.val, Trusedist_max.val, Trusedist_min.val)
    if Trad_sampling.val: st += "\t\t 'radiosity-sampling', 'stratified',\n"
    st += "\t\t 'lighting-accuracy', %f,\n" % Tlight_accur.val
    st += "\t\t 'lighting-count', %d,\n" % Tlight_count.val
    st += "\t\t 'lighting-depth', %d,\n" % Tlight_depth.val
    st += "\t\t 'lighting-threshold', %f,\n" % Tlight_thold.val
    st += "\t\t 'photon-count', %d,\n" % photon_count
    st += "\t\t 'photon-clustering-count', %d, %d\n" % (pcluster_d, pcluster_c)
    st += "\t ] )\n\n"
    file.write(st)

    if len(lamplist):
        print"Adding %d Lights:" % len(lamplist)
        for light in lamplist:
            print light
            add_lamp(light, savestuff, halocone_list)
        print "Done adding lights."
    else:
        print "No lights found"

    if len(arealist):
        print "\nAdding %d Arealights (PLIGHT):" % len(arealist)
        for area in arealist:
            print area
            add_arealight(area)
        print "Done adding Arealights."
    else:
        print "No PLIGHT arealights found"

    ################ START OF MATERIAL DEFINITIONS

    

    if Tanimation.val==2:
        # SINGLE FILE ANIMATION, WRITE MATERIALS TO SEPARATE FILE FOR EASIER EDITING
        # save the material file with extension as if it was text file, this way doubleclicking won't start python but a text editor
        matfilename = os.path.join(outdir, 'ANIM_MATERIALS.txt')
        matfile = open(matfilename, 'w')
        # ADD CODE IN THE .PY FILE TO EXECUTE THE MATERIAL STRING, LOADED EARLIER
        file.write('\t### MATERIALS ###\n')
        file.write('\texec(material_string)\n')
    else:
        # matfile is this file
        matfile = file

    

    # LIGHTFLOW DOESN'T LIKE MIXING UP OBJECTS AND MATERIALS (IE. IT CRASHES ON EXIT), SO WRITE THE MATERIALS FIRST
    matnum = 1

    

    if WORLD_LIGHT:
        # CREATE AMBIENT MATERIAL FOR DIFFUSE ILLUMINATION, POSSIBLY USING A TEXTURE
        # Convert texture if possible and needed, returns new path if converted
        if WORLD_TEX:
            texname = TEXTURE_CONVERT(WORLD_TEX)
        else:
            texname = None
        WRITE_AMBIENT(None, texname, matnum, WORLD_COLOR)

    

    # IF THERE IS AN ACTIVE WORLD WITH MIST DISTANCE>0.0, SETUP A MATERIAL AND INTERIOR FOR SIMPLE FOG
    # Blender <= 2.23 only
    MIST = 0


    if BL_VERSION<=223:        
        wd = Blender.World.GetActive()
        if wd and (wd.MisDi!=0.0):
            print "Adding Interior (Fog) sphere..."
            # another material, use backwards names plus fog_, at least make it somewhat readable...
            # no need to check if it exists, unless of course somebody actually uses these names...
            # 1.0/Mistdistance is used for the absorption factor
            st = "\n" + "### START FOG INTERIOR & MATERIAL\n\n"
            st += "horizon_color, zenith_color = vector3(%f, %f, %f), vector3(%f, %f, %f)\n\n" % (wd.HorR, wd.HorG, wd.HorB, wd.ZenR, wd.ZenG, wd.ZenB)

            

            # SCALE & TRANSLATE PATTERN TO FIT FOG SPHERE
            st += "s.transformBegin(transform().translation(vector3(0.0, 0.0, -5000.0)))\n"
            st += "s.transformBegin(transform().scaling(vector3(1.0, 1.0, 10000.0)))\n"
            st += "fog_LOROC_GOF = s.newPattern( 'linear-z', [\n"
            st += "\t'color', 0.0, zenith_color, zenith_color,\n"
            st += "\t'color', 0.5, horizon_color, horizon_color,\n"
            st += "\t'color', 1.0, zenith_color, zenith_color ] )\n"
            st += "s.transformEnd()\n"
            st += "s.transformEnd()\n\n"

            

            # ACTUAL INTERIOR
            dens = 1.0/wd.MisDi

            

            if Tvolum_toggle.val:
                # REAL VOLUMETRIC FOG, cloud interior, very very slow...
                st += "fog_ROIRETNI_GOF = s.newInterior( 'cloud', [\n"
                st += "\t\t 'kr', vector3(1.0, 1.0, 1.0),\n"
                st += "\t\t 'kr', fog_LOROC_GOF,\n"
                st += "\t\t 'kaf', %f, 'density', %f,\n" % (dens, dens)
                st += "\t\t 'sampling', %f,\n" % Tvolum_sampling.val
                st += "\t\t 'shadow-caching', vector3(-1.2, -1.2, -1.2), vector3(1.2, 1.2, 1.2),\n"
                st += "\t\t 'density-caching', %d, vector3(-1.2, -1.2, -1.2), vector3(1.2, 1.2, 1.2)\n" % Tvolum_denscach.val
                st += "\t ] )\n\n"
            else:
                # SIMPLE FOG
                st += "fog_ROIRETNI_GOF = s.newInterior( 'fog', [\n"
                st += "\t\t 'kc', vector3(1.0, 1.0, 1.0),\n"
                st += "\t\t 'kc', fog_LOROC_GOF,\n"
                st += "\t\t 'kaf', %f, 'density', 1.0\n" % dens
                st += "\t ] )\n\n"

            

            st += "s.interiorBegin(fog_ROIRETNI_GOF)\n"
            st += "fog_GOF_DLROW = s.newMaterial( 'transparent', [] )\n"
            st += "s.interiorEnd()\n\n"
            st += "### END OF FOG DEFINITION\n\n\n"

            

            matfile.write(st)
            MIST = 1

    print halocone_list

    # HALO CONE INTERIORS
    if len(halocone_list):

        hnum = 0
        # halocone = [name, height, radius, density, color, rot, loc]
        for halocone in halocone_list:


            st = "### START HALOCONE INTERIOR & MATERIAL: %s\n" % halocone[0]

            if Tvolum_toggle.val:
                # real volumetric, same interior as for fog: cloud
                st += "HALOCONE_INTR_%d = s.newInterior( 'cloud', [\n" % hnum
                st += "\t\t 'kr', vector3(1.0, 1.0, 1.0),\n"
                st += "\t\t 'kaf', %f, 'density', %f,\n" % (halocone[3], halocone[3])
                st += "\t\t 'sampling', %f,\n" % Tvolum_sampling.val
                st += "\t\t 'shadow-caching', vector3(-1.2, -1.2, -1.2), vector3(1.2, 1.2, 1.2),\n"
                st += "\t\t 'density-caching', %d, vector3(-1.2, -1.2, -1.2), vector3(1.2, 1.2, 1.2)\n" % Tvolum_denscach.val
            else:
                # non shadowing quick halo, since it is not real volumetric, needs light color
                st += "HALOCONE_INTR_%d = s.newInterior( 'halo', [\n" % hnum
                st += "\t\t 'ke', 1.0,\n"
                st += "\t\t 'kc', vector3(%f, %f, %f),\n" % halocone[4]
                st += "\t\t 'distance', %f\n" % (halocone[3]*halocone[2]*360/pi)    # intensity * 2 * cone radius for max brightness distance
            st += "\t ] )\n\n"          

            # material
            st += "s.interiorBegin(HALOCONE_INTR_%d)\n" % hnum
            st += "HALOCONE_MATR_%d = s.newMaterial( 'transparent', [] )\n" % hnum
            st += "s.interiorEnd()\n\n"
            st += "### END OF HALOCONE DEFINITION %d\n\n\n" % hnum
            matfile.write(st)
            hnum += 1

    

    ######################################################################################
    # WRITE METABALL AND NURB MATERIAL HERE

    if BFREAD_OK and Tblendimp.val and len(mball_list):

        

        # METABALLS
        # calculate TEXSPACE, using radius and position, only calculate if not done yet
        # Since metaballs in Blender behave like one object, texspace is for all combined,
        # using the first THAT HAS A MATERIAL ASSIGNED as the main metaball


        MAIN_MBALL = None   # the first with material

        bbmin = [1e100, 1e100, 1e100]
        bbmax = [-1e100, -1e100, -1e100]

        firstmb = None
        for ob in mball_list:

            

            if 'mat' in dir(ob.data):
                firstmb = ob.data
                break

        # only specified layer(s)
        if (Tlayer.val & ob.lay):

            MAIN_MBALL = ob
            obname = ob.id.name[2:]
            print "Adding MetaBall group: %s" % obname
            firstmb = ob.data

            if TEX_BOUNDS.has_key(obname):
                # already in the list
                TEXSPACE = TEX_BOUNDS[obname]
            else:
                # have to calculate
                for ob in mball_list:
                    # only specified layer(s)
                    if (Tlayer.val & ob.lay)==0: continue
                    mb = ob.data
                    obname = ob.id.name[2:]
                    mel = mb.elems.first
                    while mel:
                        t = mel.x - mel.rad
                        if t<bbmin[0]: bbmin[0] = t
                        t = mel.y - mel.rad
                        if t<bbmin[1]: bbmin[1] = t
                        t = mel.z - mel.rad
                        if t<bbmin[2]: bbmin[2] = t
                        t = mel.x + mel.rad
                        if t>bbmax[0]: bbmax[0] = t
                        t = mel.y + mel.rad
                        if t>bbmax[1]: bbmax[1] = t
                        t = mel.z + mel.rad
                        if t>bbmax[2]: bbmax[2] = t
                        mel = mel.next
                    # calculate world texture center
                    texcenter = (0.5*(bbmin[0] + bbmax[0]),
                                 0.5*(bbmin[1] + bbmax[1]),
                                 0.5*(bbmin[2] + bbmax[2]))
                    # direct matrix instead of bf matrix for animation
                    obmat = Blender.Object.Get(obname).matrix
                    texcenter = mulmatvec3x3(texcenter, obmat)
                    # translate minimum to origin,
                    # this means that bbmin can be discarded since it is always 0,0,0
                    # also offset by a small value so there will be no zero scale values
                    bbmax[0] = (bbmax[0] - bbmin[0]) + 1e-6
                    bbmax[1] = (bbmax[1] - bbmin[1]) + 1e-6
                    bbmax[2] = (bbmax[2] - bbmin[2]) + 1e-6
                TEXSPACE = (tuple(bbmax), texcenter)
                TEX_BOUNDS[obname] = TEXSPACE

            # now write material, although metaballs can have a list of more than
            # one material, it seems that only the first is actually used,
            # so only the first in the list is written here
            if ('mat' in dir(firstmb)) and len(firstmb.mat):
                material = firstmb.mat[0]
                matname = material.id.name[2:]
                WRITE_MATERIAL(BFMOD, TEXSPACE, WORLD_COLOR, matname, obname, None, None, radiosity, caustics, texture_control_list, cameraObj)
            else:
                # no material, use blender_default
                WRITE_DEFAULTMAT(radiosity)

    #--------------------------------------

    # NURB/SPLINE/SURFACE/CURVE Objects

    if BFREAD_OK and Tblendimp.val and len(nurb_list):

        for ob in nurb_list:

            # only specified layer(s)
            if (Tlayer.val & ob.lay)==0: continue

            cr = ob.data    # Curve
            nb = cr.nurb.first  # first Nurb in list

            # only export when ob is three-dimensional surface, not text/curves/paths
            dms = dir(nb)
            if not (('bp' in dms) and ('knotsu' in dms) and ('knotsv' in dms)): continue

            obname = ob.id.name[2:]
            print "Adding Curve/Surface/Nurb: %s" % obname


            # calculate TEXSPACE, using the position of the BPoint vectors,
            # only calculate if not done yet
            if TEX_BOUNDS.has_key(obname):
                TEXSPACE = TEX_BOUNDS[obname]
            else:
                bbmin = [1e100, 1e100, 1e100]
                bbmax = [-1e100, -1e100, -1e100]
                for bp in nb.bp:
                    if bp.vec[0]<bbmin[0]: bbmin[0] = bp.vec[0]
                    if bp.vec[1]<bbmin[1]: bbmin[1] = bp.vec[1]
                    if bp.vec[2]<bbmin[2]: bbmin[2] = bp.vec[2]
                    if bp.vec[0]>bbmax[0]: bbmax[0] = bp.vec[0]
                    if bp.vec[1]>bbmax[1]: bbmax[1] = bp.vec[1]
                    if bp.vec[2]>bbmax[2]: bbmax[2] = bp.vec[2]
                # calculate world texture center
                texcenter = (0.5*(bbmin[0] + bbmax[0]),
                             0.5*(bbmin[1] + bbmax[1]),
                             0.5*(bbmin[2] + bbmax[2]))
                # direct matrix instead of bf matrix for animation
                obmat = Blender.Object.Get(obname).matrix
                texcenter = mulmatvec3x3(texcenter, obmat)
                # translate minimum to origin,
                # this means that bbmin can be discarded since it is always 0,0,0
                # also offset by a small value so there will be no zero scale values
                bbmax[0] = (bbmax[0] - bbmin[0]) + 1e-6
                bbmax[1] = (bbmax[1] - bbmin[1]) + 1e-6
                bbmax[2] = (bbmax[2] - bbmin[2]) + 1e-6
                TEXSPACE = (tuple(bbmax), texcenter)
                TEX_BOUNDS[obname] = TEXSPACE

            # now write material, only the first in the list is written
            if ('mat' in dir(cr)) and len(cr.mat):
                material = cr.mat[0]
                matname = material.id.name[2:]
                WRITE_MATERIAL(BFMOD, TEXSPACE, WORLD_COLOR, matname, obname, None, None, radiosity, caustics, texture_control_list, cameraObj)
            else:
                # no material, use blender_default
                WRITE_DEFAULTMAT(radiosity)

    ######################################################################################

    

    # MESH MATERIALS
    # progressbar counter and increment
    pcount = 0
    pinc = len(meshlist)
    if pinc!=0.0:  pinc = 1.0/pinc

    
    TEXSPACE = None
    mesh_index = 0

    for mts in matrlist:

        

        pbar(pcount, 'MATERIALS...')
        pcount += pinc
        bdef = 1

        

        obname = meshlist[mesh_index]   # for arealight check below, as well as blendfile/MATSpider material, if used

        

        # if this mesh is an arealight patch without _AMBI material or it doesn't have a material,
        # don't export the material, the mesh will also not be exported
        # Stupid error, forgot inc. of mesh_index before 'continue'
        ISAREA = (obname[-6:]=='PLIGHT')

        

        print mts,ISAREA

        if (mts[0] and ISAREA and (mts[0][-5:]!='_AMBI')) or (ISAREA and not mts[0]):
    
            

            mesh_index += 1
            continue

        

        me = MESH_PT_DICT[meshlist[mesh_index]] # get mesh data

        

        # UNFORTUNATELY NEED TO CALCULATE BOUNDS OF OBJECT HERE FOR TEXTURE SPACE, CAN'T DO THIS IN MESH EXPORT LATER
        if BFREAD_OK and Tblendimp.val:
    
            
    
            # only calculate if not done yet
            if TEX_BOUNDS.has_key(obname):
                TEXSPACE = TEX_BOUNDS[obname]
            else:
                bbmin = [1e100, 1e100, 1e100]
                bbmax = [-1e100, -1e100, -1e100]
                for v in me.verts:
                    
                    # bounding box
                    if v.co[0]<bbmin[0]: bbmin[0] = v.co[0]
                    if v.co[1]<bbmin[1]: bbmin[1] = v.co[1]
                    if v.co[2]<bbmin[2]: bbmin[2] = v.co[2]

                    

                    if v.co[0]>bbmax[0]: bbmax[0] = v.co[0]
                    if v.co[1]>bbmax[1]: bbmax[1] = v.co[1]
                    if v.co[2]>bbmax[2]: bbmax[2] = v.co[2]

                

                # calculate world texture center
                texcenter = (0.5*(bbmin[0] + bbmax[0]),
                             0.5*(bbmin[1] + bbmax[1]),
                             0.5*(bbmin[2] + bbmax[2]))

                

                # To allow animation, use the matrix directly from Blender instead of the blendfile
                obmat = Blender.Object.Get(obname).matrix
                texcenter = mulmatvec3x3(texcenter, obmat)
                # translate minimum to origin,
                # this means that bbmin can be discarded since it is always 0,0,0
                # also offset by a small value so there will be no zero scale values
                bbmax[0] = (bbmax[0] - bbmin[0]) + 1e-6
                bbmax[1] = (bbmax[1] - bbmin[1]) + 1e-6
                bbmax[2] = (bbmax[2] - bbmin[2]) + 1e-6
                TEXSPACE = (tuple(bbmax), texcenter)
                TEX_BOUNDS[obname] = TEXSPACE

        

        # Get the full path to the texture (if the mesh has any textures)
        texname = GetTexturePath(me)
        # Convert texture if possible and needed, returns new path if converted
        if texname: texname = TEXTURE_CONVERT(texname)

        

        mesh_index += 1
        if (len(mts) > 0):
            for mt_index in range(len(mts)):
                if (mts[mt_index] == None):
                    bdef = 1
                else:
                    bdef = 0
                    matnum += 1
                    material_name = mts[mt_index]
                    WRITE_MATERIAL(BFMOD, TEXSPACE, WORLD_COLOR, material_name, obname, texname, matnum, radiosity, caustics, texture_control_list, cameraObj)

        

        if bdef:
            # MESH HAS NO MATERIAL, USE A DEFAULT GREY MATERIAL SIMILAR TO BLENDER'S DEFAULT
            WRITE_DEFAULTMAT(radiosity)

    # reset progressbar
    pbar(1, '')

    if Tanimation.val==2:
        # SINGLE FILE ANIMATION, CLOSE THE MATERIAL FILE
        matfile.close()

    ################ END OF MATERIAL DEFINITIONS

    # IF WORLD_LIGHT IS SET, WRITE IT NOW
    # A LIGHTFLOW SPHERE PRIMITIVE IS USED AS THE WORLD OBJECT
    if WORLD_LIGHT:
        print "Adding WORLD_LIGHT..."
        st = anim_indent + "s.materialBegin(WORLD_LIGHT)\n"
        st += anim_indent + "s.addObject( s.newObject( 'sphere', [ 'radius', %f ] ) )\n" % WORLD_SIZE
        st += anim_indent + "s.materialEnd()\n\n"
        file.write(st)

    # WRITE THE FOG SPHERE IF USED, FIXED RADIUS OF 10000.0, HOPEFULLY LARGE ENOUGH...
    if MIST:
        st = "\n" + anim_indent + "### FOG SPHERE\n"
        st += anim_indent + "s.materialBegin(fog_GOF_DLROW)\n"
        st += anim_indent + "s.addObject( s.newObject( 'sphere', [ 'radius', 10000.0 ] ) )\n"   # large enough?
        st += anim_indent + "s.materialEnd()\n\n"
        file.write(st)

    # WRITE THE HALO CONE PRIMITIVES IF USED
    hnum = 0
    # halocone = [name, height, radius, density, color, mtx]
    if len(halocone_list):
        for halocone in halocone_list:
            st = "\n" + anim_indent + "### START HALOCONE %d \n" % hnum
            if Tanimation.val==2:
                # SINGLE FILE ANIMATION, USE SAVED TRANSFORM
                st += anim_indent + "s.transformBegin(transform().setMatrix_rm(HALO_MTX%d))\n" % hnum
            else:
                st += anim_indent + "s.transformBegin(transform().setMatrix_rm(" + BMTX_TO_STRING(halocone[5]) + "))\n"
            # inner most translation needed since rotation must be around apex,
            # otherwise it will be around the base, so translate z by -height
            # Height is constant when used with single file anim
            st += anim_indent + "s.transformBegin(transform().translation( vector3(0.0, 0.0, %f) ))\n\n" % (-halocone[1])
            st += anim_indent + "s.materialBegin(HALOCONE_MATR_%d)\n" % hnum
            st += anim_indent + "s.addObject( s.newObject( 'cone', [\n"
            st += "\t\t 'height', %f,\n" % halocone[1]
            st += "\t\t 'radius', %f\n" % (halocone[1]*halocone[2])
            st += anim_indent + " ] ) )\n"
            st += anim_indent + "s.materialEnd()\n\n"
            st += 2*(anim_indent+"s.transformEnd()\n")
            st += anim_indent + "### END HALOCONE %d \n\n" % hnum
            hnum += 1
            file.write(st)

    ######################################################################################
    # EXPORT ANY METABALL AND/OR NURBS HERE

    if BFREAD_OK and Tblendimp.val:

        # metaballs, all are combined as a single object
        for mbob in mball_list:
            if (Tlayer.val & mbob.lay):
                EXPORT_LF_METABALL(mbob, MAIN_MBALL)

        # nurbs/surfaces/curves as bsplines, only if not an actual curve (only one knots list)
        for nbob in nurb_list:
            if (Tlayer.val & nbob.lay):
                dms = dir(nbob.data.nurb.first)
                if ('bp' in dms) and (('knotsu' in dms) and ('knotsv' in dms)):
                    EXPORT_LF_BSPLINE(nbob)
                else:
                    print "Object '%s' is two-dimensional, not exported" % nbob.id.name[2:]

    ######################################################################################

    # NOW WRITE THE ACTUAL MESHES
    # progressbar counter and increment
    pcount = 0
    pinc = len(meshlist)
    if pinc!=0.0:  pinc = 1.0/pinc
    matlist_index = 0
    desc = ''

    # keep track of the MATSpider material usecount as written
    MATSPIDER_WRITTEN = {}
    
    # keep track of the Blendfile material usecount as written
    BLENDFILE_WRITTEN = {}

    # meshname is actually object name
    for meshname in meshlist:

        # used material names
        mts = matrlist[matlist_index]

        pbar(pcount, ("Mesh %s" % meshname))
        pcount += pinc

        # if this mesh is an arealight patch without _AMBI material or it doesn't have a material, don't export the mesh
        # This caused errors, forgot inc. of both mesh_index in material write, and matlist_index here, before 'continue'
        ISAREA = (meshname[-6:]=='PLIGHT')
        print meshname, ISAREA, mts[0]
        if (mts[0] and ISAREA and (mts[0][-5:]!='_AMBI')) or (ISAREA and not mts[0]):
            matlist_index += 1
            continue

        # Materials are now inside transform block, so meshes with
        # more than one material don't have unnecessary separate transform blocks

        # Check if the mesh is actually unique, it might be an alt-d copy,
        # in which case it only needs to be written once
        blendobject = Blender.Object.Get(meshname)  # for matrix
        actual_meshname = MESH_PT_DICT[meshname].name
        duplimesh = (actual_meshname in meshnameslist)
        if not duplimesh: meshnameslist.append(actual_meshname)

        if Tanimation.val==2:
            # Single file anim, write transform start
            desc = "MESH: " + meshname
            WriteAnimTransform(file, 1, 1, desc)
        else:
            # Get all information from the object matrix, to assure that
            # parent transformations are correctly handled and exported.
            st = "\n#### START MESH: %s\n" % meshname
            st += "s.transformBegin( transform().setMatrix_rm(" + BMTX_TO_STRING(blendobject.matrix) + "))\n\n"
            file.write(st)

        # corresponding real (as used by meshdata itself) material indices
        midx = midxlist[matlist_index]
        matlist_index += 1
        bdef = 1
        mt_tot = len(mts)
        if mt_tot>0:
            for mt_index in range(mt_tot):
                real_mt_index = midx[mt_index]
                if (mts[mt_index] == None):
                    bdef = 1
                else:
                    bdef = 0
                    matname = STRING_CORRECT(mts[mt_index]) # correct output name
                    dupmatname = matname    # for MATSpider materials
                    print "adding mesh %s with material %s" % (meshname, matname)
                    # only on win32, change the material name for MATSpider materials, can be written multiple times, see WRITE_MATSPIDER()
                    if sys.platform=='win32':
                        if matname[-5:]=='_SPID':
                            try:
                                
                                MATSPIDER_WRITTEN[matname] += 1
                                dupmatname += ('_%d' % MATSPIDER_WRITTEN[matname])
                            except KeyError:
                                # not yet written
                                MATSPIDER_WRITTEN[matname] = 1
                    # for blendfile materials do idem as spider above
                    if Tblendimp.val:
                        try:
                            
                            BLENDFILE_WRITTEN[matname] += 1
                            dupmatname += ('_%d' % BLENDFILE_WRITTEN[matname])
                        except KeyError:
                            # not yet written
                            BLENDFILE_WRITTEN[matname] = 1
                        # compare with usecount to check if material is global, in which case the original name can be used
                        try:
                            
                            usec, isglob = BLENDFILE_USECOUNT[matname]
                        except KeyError:
                            usec, isglob = (0, 0)
                        if (usec>1) and isglob: dupmatname = matname
                    ISURF = (meshname[-5:]=='_SURF')
                    if not ISURF: file.write(anim_indent + "s.materialBegin(%s)\n" % dupmatname)
                    addmesh(duplimesh, meshname, actual_meshname, selectedList, mt_index, real_mt_index, mt_tot)
                    if ISURF:
                        meshpath = os.path.join(alldata_dir, actual_meshname+".mesh").replace('\\', '/')
                        file.write(anim_indent + "mesh_reconstruct('%s', 1).reconstruct([%s], s)\n" % (meshpath, dupmatname))
                    if not ISURF: file.write(anim_indent + 's.materialEnd()\n\n')
        if bdef:
            # mesh has no material, use default material
            print "adding mesh (default material): %s" % meshname
            file.write(anim_indent + 's.materialBegin(BLENDER_DEFAULT)\n')
            addmesh(duplimesh, meshname, actual_meshname, selectedList, -1, -1, -1)
            file.write(anim_indent + 's.materialEnd()\n\n')

        if Tanimation.val==2:
            # Write transform end
            WriteAnimTransform(file, 1, 0, desc)
        else:
            st = "s.transformEnd()\n"
            st += "### END MESH: %s\n\n" % meshname
            file.write(st)

    # reset progressbar
    pbar(1, '')


    # SCENE INFO
    print "Adding Scene info..."

    

    if Timsi_CustX.val > Timsi_CustY.val:
        aspect = float(Timsi_CustY.val) / float(Timsi_CustX.val)
        hfov = 0
    else:
        aspect = float(Timsi_CustX.val) / float(Timsi_CustY.val)
        hfov = 1

    # DEPTH OF FIELD INIT
    if FOCUS:
        if Tanimation.val==2:
            # SINGLE ANIMATION SCRIPT, INSERT CODE TO GET FOCUS POINT, CAMERA IS AFTER THIS AS LAST OBJECT
            st = "\n\t# FOCUS DISTANCE\n"
            st += "\tfcs_mtx = GetAnimData()\n"
            st += "\tFOCUS = [fcs_mtx[3][0], fcs_mtx[3][1], fcs_mtx[3][2]]\n"
            file.write(st)

    if Tanimation.val==2:
        # SINGLE ANIMATION SCRIPT, INSERT CODE TO GET CAMERA EYE, AIM & UP
        st = "\n\t# GET CAMERA EYE, AIM & UP\n"
        st += "\teye, aim, up = GetAnimData(1)\n\n"
        file.write(st)


    # USE MATRIX TO GET ROTATION, SIZE AND LOCATION, USED FOR PARENTING AND TRACKING
    # HERE infoFromMatrix IS STILL USED, SINCE NON-UNIFORM SCALING ON PARENT OF CAMERA (WHICH IS UNLIKELY TO HAPPEN ANYWAY)
    # CAN BE DONE WITHOUT AFFECTING THE CAMERA VIEW, MAKES THINGS EASIER CODE WISE TOO

    rot, size, loc = infoFromMtx(cameraObj.matrix)


    # Create the result targa image name and path
    # If this is an animation, save the targa file in image sequence directory
    # Animation targa's are in the format frame_xxxx.tga
    # As always, full path, replace backslashes with forward slashes in all paths, this is compatible with both platforms
    if Tanimation.val==1:


        cframe = Blender.Get('curframe')
        frameout_path = "'" + os.path.join(imgdir, ('frame_%04d.tga' % cframe)).replace('\\', '/') + "'"
    elif Tanimation.val==2:


        # SINGLE ANIMATION SCRIPT, INSERT CODE TO CONSTRUCT IMAGE NAME
        st = "\timgname = '" + imgdir.replace('\\', '/') + "/'"
        st += " + ('frame_%04d' % (curframe+1)) + '.tga'\n"
        file.write(st)
        frameout_path = 'imgname'
    else:


        frameout_path = "'" + os.path.join(outdir, (frame_outname + '.tga')).replace('\\', '/') + "'"


    # IMAGERS
    imager = None
    if FOCUS:

        if Tanimation.val==2:


            # SINGLE ANIMATION SCRIPT, INSERT CODE TO CALCULATE NEW FOCUS DISTANCE
            st = "\t# CALCULATE FOCUS DISTANCE\n"
            st += "\tdv = [eye[0] - FOCUS[0], eye[1] - FOCUS[1], eye[2] - FOCUS[2]]\n"
            st += "\tdistance = sqrt(dv[0]*dv[0] + dv[1]*dv[1] + dv[2]*dv[2])\n"

            if Tdof_method.val==0:


                # FAKE DOF
                if Tdof_autofocus.val:
                    # autofocus, distance calculation not needed, replace string
                    st = "\t# AUTOFOCUS MODE\n"
                    st += "\tdistance = -1.0\n"
            else:


                # REAL DOF, insert code to adjust aim point
                st += "\t# REAL DOF, AIM POINT ADJUSTMENT\n"
                st += "\taim = [aim[0] + distance*(eye[0]-aim[0]), aim[1] + distance*(eye[1]-aim[1]), aim[2] + distance*(eye[2]-aim[2])]\n"
            file.write(st)
            distst = 'distance'
        else:


            # calculate distance
            dv = [loc[0] - FOCUS[0], loc[1] - FOCUS[1], loc[2] - FOCUS[2]]
            distance = sqrt(dv[0]*dv[0] + dv[1]*dv[1] + dv[2]*dv[2])
            if (Tdof_method.val==0) and Tdof_autofocus.val:


                # FAKE DOF AUTOFOCUS, replace distance
                distance = -1.0
            distst = ("%f" % distance)
        if Tdof_method.val:
            # REAL DOF, NO IMAGER
            imager = None
        else:
            st = anim_indent + "dof = s.newImager('dof', ['depth', %s, 'radius', %f, 'mask', %d ] )\n" % (distst, Tdof_radius.val, Tdof_mask.val)
            file.write(st)
            imager = 'dof'
    # only if no imager used for dof, can these be used
    if imager==None:
        if Thalo_toggle.val:
            # Halo Imager
            st = anim_indent + "halo = s.newImager('halo', ['kr', %f, 'km', %f, 'shininess', %f ] )\n" % (Thalo_lens_kr.val, Thalo_lens_km.val, Thalo_lens_sh.val)
            file.write(st)
            imager = 'halo'
        elif Tglit_toggle.val:
            # Glitter Imager
            st = anim_indent + "glitter = s.newImager('glitter', ['radius', %f, 'intensity', %f, 'threshold', %f] )\n" % (Tglit_radius.val, Tglit_intens.val, Tglit_thold.val)
            file.write(st)
            imager = 'glitter'

    

    # EXTRA FILM IMAGER, CAN USE ANOTHER IMAGER
    if Tfilm_toggle.val:
        st = anim_indent + "film = s.newImager('film', ['grain', %f" % Tfilm_grain.val
        if imager: st += ", 'imager', %s" % imager
        st += " ] )\n"
        file.write(st)
        imager = 'film'

    


    # FINAL IMAGER (SAVER)
    if imager:
        st = anim_indent + "saver = s.newImager('tga-saver', [ 'file', %s, 'imager', %s ] )\n\n" % (frameout_path, imager)
        file.write(st)
    else:
        st = "\n" + anim_indent + "saver = s.newImager('tga-saver', [ 'file', %s, 'alpha', 0, 'depth', 0])\n\n" % frameout_path
        file.write(st)

    

    file.write(anim_indent + "s.imagerBegin( saver )\n\n")
    st = anim_indent + "camera = s.newCamera( 'pinhole', [\n"

    

    if Tanimation.val==2:
    
        

        # SINGLE ANIMATION SCRIPT, USE DATA
        st += "\t\t 'eye', vector3(eye[0], eye[1], eye[2]),\n"
        st += "\t\t 'aim', vector3(aim[0], aim[1], aim[2]),\n"
        st += "\t\t 'up', vector3(up[0], up[1], up[2]),\n"
    else:

        

        isy, isz = size[1], size[2]
        if isy!=0.0: isy = 1.0/isy
        if isz!=0.0: isz = -1.0/isz

        

        up = (cameraObj.matrix[1][0]*isy, cameraObj.matrix[1][1]*isy, cameraObj.matrix[1][2]*isy)
        lookdir = (cameraObj.matrix[2][0]*isz, cameraObj.matrix[2][1]*isz, cameraObj.matrix[2][2]*isz)

        

        if (Tdof_method.val==0) or (FOCUS==None):
            distance = 1.0  # distance not used here with fake DoF or no DoF at all

        

        lookAt = (loc[0] + distance * lookdir[0], loc[1] + distance * lookdir[1], loc[2] + distance * lookdir[2])
        # need 'up' vector too

        

        st += "\t\t 'eye', vector3(%f, %f, %f),\n" % loc
        st += "\t\t 'aim', vector3(%f, %f, %f),\n" % lookAt
        st += "\t\t 'up', vector3(%f, %f, %f),\n" % up
    
        

    if FOCUS and Tdof_method.val:
        # Real Depth Of Field, write aperture
        st += "\t\t 'aperture', %f,\n" % Tdof_aperture.val

    # ANTI-ALIASING PARAMETERS
    st += "\t\t 'aa-samples', %d, %d, 'aa-threshold', %f, 'aa-jitter', %f,\n" % (Taa_samples1.val, Taa_samples2.val, Taa_thold.val, Taa_jitter.val)
    st += "\t\t 'fov', "
    if hfov: st += "'horizontal', "

    
## jms : modif for 228
    if BL_VERSION<228:
        st += "%f\n" % (2.0*atan(aspect * 16.0 / camera.Lens))
    else:
        st += "%f\n" % (2.0*atan(aspect * 16.0 / camera.lens))
## jms : modif for 228
    

    st += "\t ] )\n\n"
    file.write(st)
    file.write(anim_indent + "s.imagerEnd()\n\n")
    if caustics or radiosity:
        file.write(anim_indent + "s.radiosity()\n")
    file.write(anim_indent + "s.render(camera, %d, %d)\n" % (Timsi_CustX.val, Timsi_CustY.val))

    if Tanimation.val==2:
        # SINGLE ANIMATION SCRIPT, ADD CODE TO DELETE THE SCENE
        # THIS IS NECESSARY OTHERWISE ALL OBJECTS WILL BE DUPLICATED
        file.write("\n\t# Prepare for new frame by deleting the scene\n")
        file.write('\tdel s\n')

    print "Done adding Scene info"

    file.close()

    # If this is a single file animation export, get and save the animation data
    if Tanimation.val==2:
        print "Getting animation data for all exported objects for all frames..."
        # Create total list of exported object names
        # in order: lamps, arealights, texture controls, meshes, focus & camera as function argument
        oblist = []
        oblist.extend(lamplist)
        oblist.extend(arealist)
        oblist.extend(texture_control_list)
        oblist.extend(meshlist)

        if FOCUS: oblist.extend(['FOCUS'])

        if BL_VERSION>223:
            animdat = AnimPack().PackAllFrames(oblist, camera.name)
        elif BL_VERSION>228:
            animdat = AnimPack().PackAllFrames(oblist, cameraObj.data)
        else:
            animdat = AnimPack().PackAllFrames(oblist, cameraObj.getName())
        
        datname = os.path.join(alldata_dir, 'ANIMATION.dat')

        file = open(datname, 'wb')
        file.write(animdat)
        file.close()
        
        print 'Saved animation data as: '+datname
    
    print "This is the End...."
    
    print
    sys.stdout.flush()

    return len(meshlist), len(arealist)+len(lamplist)


# WINDOWSIZE USED FOR ALL GUIS
def GetWindowFactors():
    # Get the viewport size to make the buttons fit the window
    wsize = BGL.Buffer(BGL.GL_INT, 4)
    BGL.glGetIntegerv(BGL.GL_VIEWPORT, wsize)
    # original 'design' window size w,h: 361, 398
    # later, needed more space: 393, 510
    # coord multiply values for any window size
    #return max(1,int(wsize[2]*0.5)), max(1,int(wsize[2]/393.0)), max(1,int(wsize[3]/510.0))
    return max(1,int(wsize[2]*0.5)), max(1,int(wsize[2]/393.0)), max(1,int(wsize[3]/510.0))


##################################################
# draw SUBROUTINE FOR THE MAIN GUI               #
##################################################

def main_draw():
    global Tsavestuff, Tautocheck, Tradiosity, Tcaustics, Tanimation, Tblendimp
    global TWORLD_LIGHT, TWORLD_SIZE, TWORLD_COLOR_R, TWORLD_COLOR_G, TWORLD_COLOR_B, TWORLD_TEX
    global Ttrace_depth, Tradio_depth, Tradio_samples
    global Tphoton_count, Tpcluster_d, Tpcluster_c
    global Tlayer
    # anti-alias
    global Taa_samples1, Taa_samples2, Taa_thold, Taa_jitter
    global Trender_preset
    # doc menu
    global Tdocmenu
    # image size
    global Timsi_pref, Timsi_percent, Timsi_CustX, Timsi_CustY

    # get the window coordinate multiply factors
    midx, mulx, muly = GetWindowFactors()
    midx = int((393*mulx)/2)
    # clear screen
    getBGC()
    BGL.glClear(BGL.GL_COLOR_BUFFER_BIT)

    # background title box
    BGL.glColor3f(0, 0, 0)
    BGL.glRecti(0, 480*muly, 393*mulx, 510*muly)

    Title = "LIGHTFLOW EXPORT" +" "+LFE_ID
    BGL.glColor3f(0.42, 0.378, 0.387)
    BGL.glRasterPos2i(midx - len(Title)*3.5, 490*muly)
    Draw.Text(Title)
    BGL.glColor3f(1, 1, 0.75)
    BGL.glRasterPos2i(midx - len(Title)*3.5-2, 490*muly+2)
    Draw.Text(Title)

    st = "Begun by Montz, enhanced by Eeshlo, cosmetics started by S68"
    BGL.glColor3f(0.5, 0.25, 0.125)
    BGL.glRasterPos2i(midx - len(st)*3.15, 460*muly)
    Draw.Text(st)

    # BUTTON TO ALLOW REDEFINITON OF PATHS/PREFERENCES
    Draw.Button("PREFS", evt_redefpref, 340*mulx, 430*muly, 40*mulx, 18*muly, "Redefine paths/preferences")
    
    BGL.glColor3f(0, 0, 0)
    BGL.glRasterPos2i(8*mulx, 435*muly)
    Draw.Text("BASICS:")

    BGL.glRasterPos2i(171*mulx - 148, 415*muly)
    Draw.Text("Shadow & radiosity data")
    
    # Save data menu, when animation is enabled, add extra option for first frame optim.
    mstr = "Calculation data?%t|Don't care%x0|Save%x1|Load%x2"
    if Tanimation.val!=0: mstr += "|(ANIM) save then load%x3"
    Tsavestuff  = Draw.Menu(mstr, evt_ignore, 175*mulx, 410*muly, 205*mulx, 18*muly, Tsavestuff.val,
                    "Defines what to do with shadowmap and radiosity data" )

    BGL.glRasterPos2i(170*mulx - 64, 395*muly)
    Draw.Text("Mesh files")
    st = "Mesh files%t|Always write%x0|Check if it exists first%x1"
    # If render-from-blender-anim, add an extra option to only export the selected meshes
    # This is necessary since Blender's memory usage of the Getraw function can make things quite unusable
    if Tanimation.val==1: st += "|(ANIM) Export selected only%x2"
    Tautocheck  = Draw.Menu(st, evt_ignore, 175*mulx, 390*muly, 205*mulx, 18*muly, Tautocheck.val, "Mesh files")

    Tradiosity  = Draw.Toggle("Radiosity: "+TGSTATE[Tradiosity.val], evt_TGredraw, 10*mulx, 370*muly, 70*mulx, 18*muly, Tradiosity.val,
                    "Enables/disables radiosity calculations")
    Tcaustics   = Draw.Toggle("Caustics: "+TGSTATE[Tcaustics.val], evt_TGredraw, 80*mulx, 370*muly, 70*mulx, 18*muly, Tcaustics.val,
                    "Enables/disables caustics calculations")
    Tanimation  = Draw.Menu("What to export?%t|Export this frame%x0|Export & Render entire anim%x1|Export single file anim%x2",
                    evt_anim, 150*mulx, 370*muly, 230*mulx, 18*muly, Tanimation.val,
                    "What to export?")

    TWORLD_LIGHT    = Draw.Toggle("World Light: "+TGSTATE[TWORLD_LIGHT.val], evt_world, 10*mulx, 290*muly, 98*mulx, 78*muly, TWORLD_LIGHT.val,
                        "Enables/disables Arnold type global illumination")
    # only draw the remaining world buttons when the main button is set
    if TWORLD_LIGHT.val:
        TWORLD_COLOR_R  = Draw.Slider("R: ", evt_ignore, 130*mulx, 350*muly, 150*mulx, 18*muly, TWORLD_COLOR_R.val, 0.0, 5.0, 1,
                            "World light color, red component")
        TWORLD_COLOR_G  = Draw.Slider("G: ", evt_ignore, 130*mulx, 330*muly, 150*mulx, 18*muly, TWORLD_COLOR_G.val, 0.0, 5.0, 1,
                            "World light color, green component")
        TWORLD_COLOR_B  = Draw.Slider("B: ", evt_ignore, 130*mulx, 310*muly, 150*mulx, 18*muly, TWORLD_COLOR_B.val, 0.0, 5.0, 1,
                            "World light color, blue component")
        # display a color matching the sliders, by scaling with maximum
        r, g , b = TWORLD_COLOR_R.val, TWORLD_COLOR_G.val, TWORLD_COLOR_B.val
        maxintens = max(r, g, b)
        if maxintens>1.0:
            maxintens = 1.0/maxintens
            r *= maxintens;  g *= maxintens;  b *= maxintens
        BGL.glColor3f(r, g, b)
        BGL.glRecti(112*mulx, 312*muly, 128*mulx, 366*muly)
        TWORLD_SIZE     = Draw.Number("Size: ", evt_ignore, 110*mulx, 290*muly, 170*mulx, 18*muly, TWORLD_SIZE.val, 0.01, 10000.0,
                            "World light, radius of light sphere")
        # world texture file select button, no available for versions >223
        if BL_VERSION<=223:
            Draw.Button("FSEL", evt_fseltex, 10*mulx, 270*muly, 50*mulx, 18*muly, "Use File Selector to find a world texture")
        TWORLD_TEX      = Draw.String("Texture: ", evt_ignore, 60*mulx, 270*muly, 320*mulx, 18*muly, TWORLD_TEX.val, 128,
                            "World Light Texture (spherical .tga, full path)")

    # RENDER BUTTON SCREEN SWITCH, no python dependency anymore
    # formerly only displayed when a scene was exported at least once
    # On request of 'fullback' always visible
    # It WILL be disabled when 'single file animation' option is chosen, since that is meant to run on it's own
    if Tanimation.val!=2:
        Draw.Button("RENDER", evt_rendscr, 282*mulx, 290*muly, 98*mulx, 78*muly, "Switch to render screen")

    # Button for popup window to set export layers
    Draw.Button("LAYERS", evt_layerwin, 10*mulx, 250*muly, 121*mulx, 18*muly, "Which layer to export?")

    # Edit python file button, not available when render-from-blender animation enabled
    if Tanimation.val!=1:
        Draw.Button("EDIT .py", evt_pyedit, 135*mulx, 250*muly, 121*mulx, 18*muly, "Edit the python file")

    # SCREEN TO ADD IMAGERS AND SET DOF OPTIONS
    Draw.Button("IMAGERS", evt_imgdof, 260*mulx, 250*muly, 120*mulx, 18*muly, "Add special imagers and set DOF options")

    # If MSPint module was sucessfully imported, add two buttons to display MATSpider material library palette
    if MSPOK:
        Draw.Button("MATSpider: Materials Only", evt_MSPMATWIN, 10*mulx, 230*muly, 195*mulx, 18*muly, "Show MATSpider Library materials only")
        Draw.Button("MATSpider: Entire Library", evt_MSPLIBWIN, 10*mulx, 210*muly, 195*mulx, 18*muly, "Show MATSpider complete Library contents")

    # SPECIAL OPTION, IMPORT MATERIALS FROM BLENDFILE, only available if module sucessfully imported
    if BFREAD_OK:
        Tblendimp = Draw.Toggle("Blendfile Import: "+TGSTATE[Tblendimp.val], evt_TGredraw, 210*mulx, 230*muly, 170*mulx, 18*muly, Tblendimp.val, "Import Materials/Nurbs/MetaBalls from blendfile, save file first!")

    # suggestion by "hannibar", button to Lightflow Docs, now generalized as menu to all docs
    st = "DOCUMENTATION%x0|Lightflow%x1|Install info  & Credits%x2|This Script%x3|Blendfile import%x4"
    # MATSpider docs not relevant on Linux or when MSPint not imported
    if MSPOK: st += "|MATSpider Tutorial%x5"
    Tdocmenu = Draw.Menu(st, evt_shoDOCS, 210*mulx, 210*muly, 170*mulx ,18*muly, Tdocmenu.val, "Browse documentation")

    # RENDER IMAGE SIZE SETTINGS
    BGL.glColor3f(0, 0, 0)
    BGL.glRasterPos2i(8*mulx, 193*muly)
    Draw.Text("IMAGE SIZE:")
    st = 'RENDER IMAGE SIZE%t| 4:3 -> 640 X 480%x0|16:9 -> 640 X 360%x1|Custom%x2'
    # image settings not available in Publisher
    if BL_VERSION <= 223: st += '|FROM BLENDER%x3'
    Timsi_pref = Draw.Menu(st, evt_imgsize, 75*mulx, 190*muly, 130*mulx, 18*muly, Timsi_pref.val, "Render Image Size Settings")

    if Timsi_pref.val!=2:
        st = "Image Size Percentage%t|10 % %x10|25 % %x25|50 % %x50|75 % %x75|100 % %x100|125 % %x125|150 % %x150|175 % %x175|200 % %x200"
        Timsi_percent = Draw.Menu(st, evt_imgsize, 210*mulx, 190*muly, 60*mulx, 18*muly, Timsi_percent.val, "Image Size Percentage")
        # Display real size
        BGL.glColor3f(1, 1, 0)
        BGL.glRasterPos2i(275*mulx, 193*muly)
        st = "-> %d X %d" % (Timsi_CustX.val, Timsi_CustY.val)
        Draw.Text(st)
    else:
        Timsi_CustX = Draw.Number("X: ", evt_ignore, 210*mulx, 190*muly, 82*mulx, 18*muly, Timsi_CustX.val, 10, 4096, "X Resolution")
        Timsi_CustY = Draw.Number("Y: ", evt_ignore, 292*mulx, 190*muly, 83*mulx, 18*muly, Timsi_CustY.val, 10, 4096, "Y Resolution")

    # ADVANCED SETTINGS
    BGL.glColor3f(0, 0, 0)
    BGL.glRasterPos2i(8*mulx, 173*muly)
    Draw.Text("ADVANCED:")

    # BUTTON TO RESET ALL SETTINGS TO DEFAULT, always available
    Draw.Button("RESET ALL", evt_reset, 235*mulx, 170*muly, 145*mulx, 18*muly, "Reset all parameters to default")

    # display remainder of GUI only if render preset is 'user' or 'default'
    if Trender_preset.val<2:

        # SCREEN TO EVEN MORE RENDER-ENGINE OPTIONS
        Draw.Button("MORE PARAMETERS", evt_morpar, 83*mulx, 170*muly, 150*mulx, 18*muly, "Set more render-engine parameters")

        Ttrace_depth    = Draw.Slider("Trc depth: ", evt_ignore, 10*mulx, 150*muly, 182*mulx, 18*muly, Ttrace_depth.val, 0, 16, 1,
                            "maximum number of reflect/refract bounces")
        Tradio_depth    = Draw.Slider("Rad depth: ", evt_ignore, 197*mulx, 150*muly, 182*mulx, 18*muly, Tradio_depth.val, 0, 16, 1,
                            "maximum number of radiosity diffuse/specular bounces")
        Tradio_samples  = Draw.Number("Radiosity samples: ", evt_ignore, 10*mulx, 130*muly, 182*mulx, 18*muly, Tradio_samples.val, 10, 100000,
                            "rays used for radiosity computations at each spatial location")
        Tphoton_count   = Draw.Number("Photon Count: ", evt_ignore, 197*mulx, 130*muly, 182*mulx, 18*muly, Tphoton_count.val, 100, 10000000,
                            "The number of photons spread out into the scene")
        Tpcluster_d     = Draw.Number("PhDiffuse: ", evt_ignore, 10*mulx, 110*muly, 182*mulx, 18*muly, Tpcluster_d.val, 5, 10000,
                            "Diffuse photon-clustering-count")
        Tpcluster_c     = Draw.Number("PhCaustic: ", evt_ignore, 197*mulx, 110*muly, 182*mulx, 18*muly, Tpcluster_c.val, 5, 1000,
                            "Caustics photon-clustering-count")

        # CAMERA ANTI-ALIASING OPTIONS
        BGL.glColor3f(0, 0, 0)
        BGL.glRasterPos2i(8*mulx, 95*muly)
        Draw.Text("ANTI-ALIASING:")
        Taa_samples1    = Draw.Number("Smp1: ", evt_ignore, 10*mulx, 75*muly, 90*mulx, 18*muly, Taa_samples1.val, 1, 10,
                            "Square root of samples taken every pixel")
        Taa_samples2    = Draw.Number("Smp2: ", evt_ignore, 103*mulx, 75*muly, 90*mulx, 18*muly, Taa_samples2.val, 1, 10,
                            "Supersampling factor")
        Taa_thold       = Draw.Number("Thold: ", evt_ignore, 197*mulx, 75*muly, 90*mulx, 18*muly, Taa_thold.val, 0.0, 3.0,
                            "supersampling threshold level")
        Taa_jitter      = Draw.Number("Jitter: ", evt_ignore, 290*mulx, 75*muly, 90*mulx, 18*muly, Taa_jitter.val, 0.0, 1.0,
                            "Random jitter amount")

    # PRESET RENDER SETTINGS MENU
    BGL.glColor3f(0, 0, 0)
    BGL.glRasterPos2i(200*mulx, 55*muly)
    Draw.Text("RENDER PRESETS")
    mst = "RENDER PRESETS%t|User Settings%x0|Defaults%x1|Fast Preview%x2|Fast Caustics%x3|Fast Radiosity%x4|Fast Caustics & Radiosity%x5|Precise Caustics%x6|Precise Radiosity%x7|Precise Caustics & Radiosity%x8"
    Trender_preset  = Draw.Menu(mst, evt_preset, 193*mulx, 35*muly, 187*mulx, 18*muly, Trender_preset.val,
                            "Render engine parameter presets")

    BGL.glColor3f(0, 0, 0)
    BGL.glRecti(10*mulx, 33*muly, 190*mulx, 53*muly)
    if EXPORT_FAILED==2:
        # no objects where exported
        BGL.glColor3f(1,0.5,0)
        BGL.glRasterPos2i(14*mulx, 40*muly)
        Draw.Text("Warning: no objects exported!")
    
    elif EXPORT_FAILED==3:
        # no lights (or world_light) were exported
        BGL.glColor3f(1,0.5,0)
        BGL.glRasterPos2i(14*mulx, 40*muly)
        Draw.Text("Warning: no lights exported!")

    elif EXPORT_FAILED==4:
        # Not a real export failure, just can't find the requested documentation
        BGL.glColor3f(1,0.5,0)
        BGL.glRasterPos2i(14*mulx, 40*muly)
        Draw.Text("Warning: Can't find docs !")

    elif EXPORT_FAILED!=0:
        # real export failure, could happen, file errors can happen, or maybe something is not recognized by the script...
        BGL.glColor3f(1,0,0)
        BGL.glRasterPos2i(14*mulx, 40*muly)
        Draw.Text("ERROR: EXPORT FAILED!")

    else:
        # display status
        if WORKING:
            BGL.glColor3f(1, 0, 0)
            BGL.glRasterPos2i(18*mulx, 40*muly)
            Draw.Text("EXPORTING...")
        else:
            BGL.glColor3f(0, 1, 0)
            BGL.glRasterPos2i(36*mulx, 40*muly)
            Draw.Text("Ready!")

    # Exit button
    Draw.Button("Exit", evt_exit, 10*mulx, 10*muly, 172*mulx, 18*muly)

    # THE Export Button, not for render-from-blender animation
    if Tanimation.val!=1:
        Draw.Button("Export", evt_export, 193*mulx, 10*muly, 187*mulx, 18*muly)


def main_event(evt, val):
    if (evt==Draw.QKEY) and (not val):
        SCRIPT_EXIT()


# Opens the specified webbrowser on Linux, IE on windows
def BROWSER_OPEN(filename):
    if sys.platform=="win32":
        # just use webbrowser directly
        webbrowser.open(filename)
    else:
        # ord.: def/konq/mozz/nets
        if Tbrowser.val==0:
            # default (probably lynx)
            webbrowser.open(filename)
        elif Tbrowser.val==1:
            wb = webbrowser.Konquerer()
            wb.open(filename)
        elif Tbrowser.val==2:
            # not in webbrowser module, use os.system, will disable Blender until closed though...
            cmd = "mozilla file://" + filename
            os.system(cmd)
        else:
            wb = webbrowser.Netscape()
            wb.open(filename)


def main_bevent(evt):
    global Tsavestuff, Tautocheck, Tradiosity, Tcaustics, Tanimation
    global TWORLD_LIGHT, TWORLD_SIZE, TWORLD_COLOR_R, TWORLD_COLOR_G, TWORLD_COLOR_B, TWORLD_TEX
    global Ttrace_depth, Tradio_depth, Tradio_samples
    global Tphoton_count, Tpcluster_d, Tpcluster_c
    global WORKING, NO_FILES, EXPORT_FAILED
    global file, meshfile, matfile
    global Tlayer
    # anti-alias
    global Taa_samples1, Taa_samples2, Taa_thold, Taa_jitter
    # default engine
    global Tdisp_switch, Tshad_switch, Tvolm_switch
    global Trad_sampling, Trad_thold, Trusedist_scr, Trusedist_max, Trusedist_min
    global Tlight_accur, Tlight_count, Tlight_depth, Tlight_thold
    global Trender_preset
    # imager switches
    global Tglit_toggle, Thalo_toggle, Tfilm_toggle, Tdof_method, Tvolum_toggle
    # docmenu
    global Tdocmenu
    # path redefine
    global PATH_OK, PREF_CANCEL
    # image size
    global Timsi_CustX, Timsi_CustY, Timsi_percent
    global REND_MSG, RENDER_STARTED

    if evt == evt_exit:
        SCRIPT_EXIT()
    elif evt == evt_layerwin:
        # start the layer activation GUI
        Draw.Register(LY_draw, main_event, LY_bevent)
    elif evt == evt_export:
        WORKING = 1

## jms : modif 16/08/2003
        if BL_VERSION<228:   
            Blender.Window.Redraw(Blender.Window.Const.TEXT)
        else:
            Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003

        EXPORT_FAILED = 0

        # try to export, if anything fails, make sure the file is closed
        try:
            
            # get the image size here again, in case it changed
            if Timsi_pref.val==3:
                if  BL_VERSION<=223: 
                    ds = Blender210.getDisplaySettings()
                    pf = Timsi_percent.val * 0.01
                    Timsi_CustX.val = pf * ds.xResolution
                    Timsi_CustY.val = pf * ds.yResolution
                    Blender.Redraw()    # display it
            
            # time it
            numobs, numlamps = ExportIt()
            
            if numobs==0: EXPORT_FAILED = 2 # WARNING, no objects exported
            if (numlamps==0) and (TWORLD_LIGHT.val==0): EXPORT_FAILED = 3   # WARNING, no lights exported
        except IOError:
            # close file, meshfile and/or matfile if open and defined
            ShowError()
            try:
                
                if not file.closed:
                    print "Python export file write failure"
                    file.close()
                if not meshfile.closed:
                    print "Meshfile write failure"
                    meshfile.close()
                if not matfile.closed:
                    print "Materialfile write failure"
                    matfile.close()
            except:
                pass
            # repair progressbar, might be half displayed
            pbar(1 ,'')
            EXPORT_FAILED = 1
        except:
            ShowError()
            # repair progressbar, might be half displayed
            pbar(1 ,'')
            EXPORT_FAILED = 1
        sys.stdout.flush()  # just in case, for win
        WORKING = 0
        NO_FILES = 0
## jms : modif 16/08/2003
        if BL_VERSION<228:   
            Blender.Window.Redraw(Blender.Window.Const.TEXT)
        else:
            Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003
    elif evt == evt_world:
        # hide the world buttons when not used
        Blender.Redraw()
    elif evt == evt_reset:
        # reset all parameters to the default values
        SetDefaults()
        Blender.Redraw()
    elif evt == evt_rendscr:
        # switch to render GUI,
        # but first check if Lightflow was started before that, as it still might be running
        REND_MSG, activity = LFRUNNING()
        if activity!=1:
            REND_MSG = 'Ready!'
            RENDER_STARTED = 0
        else:
            # if LFPID!=-1 still running, use message from LFRUNNING(),
            # otherwise it was not possible to determine yet
            if LFPID!=-1:
                RENDER_STARTED = 1
            else:
                RENDER_STARTED = 0
        # load in the last targa file if there is one,
        # but only if fast display is possible, otherwise it takes to long to switch
        if fast_display_ok: LoadRawTGA()
        Draw.Register(rd_draw, rd_event, rd_bevent)
    elif evt == evt_pyedit:
        GetOutdir()
        if os.path.exists(pyfilepath):
            try:
                
                if sys.platform=='win32':
                    os.spawnv(os.P_NOWAIT, os.path.join(os.environ['WINDIR'], Teditpath.val), [' '+pyfilepath])
                else:
                    os.system(Teditpath.val + ' ' + pyfilepath)
            except:
                print "Could not start editor"
        else:
            print "%s does not exist" % pyname
    elif evt == evt_anim:
        # If switching Export menu from 'anim' to 'this frame', reset savestuff menu
        if (Tanimation.val==0) and (Tsavestuff.val==3):
            Tsavestuff = Draw.Create(0)
        # If switching Export menu from 'render & export anim' to 'this frame' or 'single file anim'
        # reset autocheck menu, when set to 'export selected'
        if (Tanimation.val!=1) and (Tautocheck.val==2):
            Tautocheck = Draw.Create(0)
        # redraw screen with 'Export' and 'EDIT' buttons disabled
        Blender.Redraw()
    elif evt == evt_MSPMATWIN:
        # No need to place in try/except, events only happen when MSPint was succesfully imported at all (no buttons otherwise)
        MSPint.ShowMATPalette(1)
        # need to redraw, old palette image can still be visible
        Blender.Redraw()
    elif evt == evt_MSPLIBWIN:
        MSPint.ShowMATPalette(0)
        # need to redraw, old palette image can still be visible
        Blender.Redraw()
    elif evt == evt_imgdof:
        # Switch to imagers/dof screen
        Draw.Register(xtr_draw, main_event, xtr_bevent)
    elif evt == evt_fseltex:
        FileSelect_TEX()
    elif evt == evt_morpar:
        # Switch screen to change more render-engine parameters
        Draw.Register(mp_draw, main_event, mp_bevent)
    elif evt == evt_preset:
        # Set parameters according to preset
        if Trender_preset.val == 1:
            # Default settings (engine only)
            Tradiosity.val      =   0
            Tcaustics.val       =   0
            Ttrace_depth.val    =   4
            Tradio_depth.val    =   4
            Tradio_samples.val  =   400
            Tphoton_count.val   =   300000
            Tpcluster_d.val     =   1000
            Tpcluster_c.val     =   50
            Tdisp_switch.val    =   1
            Tshad_switch.val    =   1
            Tvolm_switch.val    =   1
            Trad_sampling.val   =   0   # Default sampling
            Trad_thold.val      =   0.2
            Trusedist_scr.val   =   0.25
            Trusedist_max.val   =   0.4
            Trusedist_min.val   =   0.01
            Tlight_accur.val    =   0.98
            Tlight_count.val    =   1
            Tlight_depth.val    =   5
            Tlight_thold.val    =   0.05
            Taa_samples1.val    =   2
            Taa_samples2.val    =   4
            Taa_thold.val       =   0.07
            Taa_jitter.val      =   0.5
            # cache settings
            Tcache_switch.val   =   0
            Tcache_size.val     =   1000
            Tcache_cells.val    =   100
            Tcache_minrad.val   =   0.1
            Tcache_maxrad.val   =   0.3
        elif Trender_preset.val == 2:
            # Fast preview
            Tradiosity.val      =   0
            Tcaustics.val       =   0
            Ttrace_depth.val    =   1
            Tradio_depth.val    =   0
            # rad.params not used, so no need to set
            Tdisp_switch.val    =   0
            Tshad_switch.val    =   0
            Tvolm_switch.val    =   0
            Taa_samples1.val    =   1
            Taa_samples2.val    =   1
            Taa_thold.val       =   3.0
            Taa_jitter.val      =   0.0
            # disable all imagers (fake dof will still be done however, if used)
            Tglit_toggle.val    =   0
            Thalo_toggle.val    =   0
            Tfilm_toggle.val    =   0
            Tdof_method.val     =   0
            Tvolum_toggle.val   =   0
            # cache settings
            Tcache_switch.val   =   1
            Tcache_size.val     =   1000
            Tcache_cells.val    =   100
            Tcache_minrad.val   =   0.1
            Tcache_maxrad.val   =   0.3
        elif Trender_preset.val == 3:
            # Fast caustics
            Tradiosity.val      =   0
            Tcaustics.val       =   1
            Ttrace_depth.val    =   4
            Tradio_depth.val    =   4
            Tphoton_count.val   =   30000
            Tpcluster_c.val     =   10
            Tdisp_switch.val    =   0
            Tshad_switch.val    =   1
            Tvolm_switch.val    =   0
            Trad_sampling.val   =   0   # Default sampling
            Trad_thold.val      =   0.2
            Taa_samples1.val    =   2
            Taa_samples2.val    =   3
            Taa_thold.val       =   0.25    # slightly faster AA
            Taa_jitter.val      =   0.0
            # disable all imagers
            Tglit_toggle.val    =   0
            Thalo_toggle.val    =   0
            Tfilm_toggle.val    =   0
            Tdof_method.val     =   0
            Tvolum_toggle.val   =   0
            # cache settings
            Tcache_switch.val   =   1
            Tcache_size.val     =   1000
            Tcache_cells.val    =   100
            Tcache_minrad.val   =   0.1
            Tcache_maxrad.val   =   0.3
        elif Trender_preset.val == 4:
            # Fast radiosity
            Tradiosity.val      =   1
            Tcaustics.val       =   0
            Ttrace_depth.val    =   4
            Tradio_depth.val    =   4
            Tradio_samples.val  =   100
            Tphoton_count.val   =   30000
            Tpcluster_d.val     =   250
            Tdisp_switch.val    =   0
            Tshad_switch.val    =   1
            Tvolm_switch.val    =   0
            Trad_sampling.val   =   0   # Default sampling
            Trad_thold.val      =   0.2
            Trusedist_scr.val   =   0.25
            Trusedist_max.val   =   0.4
            Trusedist_min.val   =   0.01
            Taa_samples1.val    =   2
            Taa_samples2.val    =   3
            Taa_thold.val       =   0.25    # slightly faster AA
            Taa_jitter.val      =   0.0
            # disable all imagers
            Tglit_toggle.val    =   0
            Thalo_toggle.val    =   0
            Tfilm_toggle.val    =   0
            Tdof_method.val     =   0
            Tvolum_toggle.val   =   0
            # cache settings
            Tcache_switch.val   =   1
            Tcache_size.val     =   1000
            Tcache_cells.val    =   100
            Tcache_minrad.val   =   0.1
            Tcache_maxrad.val   =   0.3
        elif Trender_preset.val == 5:
            # Fast radiosity & caustics
            Tradiosity.val      =   1
            Tcaustics.val       =   1
            Ttrace_depth.val    =   4
            Tradio_depth.val    =   4
            Tradio_samples.val  =   100
            Tphoton_count.val   =   30000
            Tpcluster_d.val     =   250
            Tpcluster_c.val     =   10
            Tdisp_switch.val    =   0
            Tshad_switch.val    =   1
            Tvolm_switch.val    =   0
            Trad_sampling.val   =   0   # Default sampling
            Trad_thold.val      =   0.2
            Trusedist_scr.val   =   0.25
            Trusedist_max.val   =   0.4
            Trusedist_min.val   =   0.01
            Taa_samples1.val    =   2
            Taa_samples2.val    =   3
            Taa_thold.val       =   0.25
            Taa_jitter.val      =   0.0 
            # disable all imagers
            Tglit_toggle.val    =   0
            Thalo_toggle.val    =   0
            Tfilm_toggle.val    =   0
            Tdof_method.val     =   0
            Tvolum_toggle.val   =   0
            # cache settings
            Tcache_switch.val   =   1
            Tcache_size.val     =   1000
            Tcache_cells.val    =   100
            Tcache_minrad.val   =   0.1
            Tcache_maxrad.val   =   0.3
        elif Trender_preset.val == 6:
            # Slow and precise caustics
            Tradiosity.val      =   0
            Tcaustics.val       =   1
            Ttrace_depth.val    =   6
            Tphoton_count.val   =   1000000
            Tpcluster_c.val     =   250     # maybe be too smooth?
            Tdisp_switch.val    =   1
            Tshad_switch.val    =   1
            Tvolm_switch.val    =   1
            Taa_samples1.val    =   2
            Taa_samples2.val    =   4
            Taa_thold.val       =   0.07
            Taa_jitter.val      =   0.5
            # cache settings (off) (although it might be faster with, without any degradation)
            Tcache_switch.val   =   0
        elif Trender_preset.val == 7:
            # Slow and precise radiosity
            Tradiosity.val      =   0
            Tcaustics.val       =   1
            Ttrace_depth.val    =   6
            Tradio_depth.val    =   6
            Tradio_samples.val  =   5000
            Tphoton_count.val   =   1000000
            Tpcluster_d.val     =   2500    # too large?
            Tdisp_switch.val    =   1
            Tshad_switch.val    =   1
            Tvolm_switch.val    =   1
            Trad_sampling.val   =   1   # Stratified sampling
            Trad_thold.val      =   0.2
            Trusedist_scr.val   =   0.25
            Trusedist_max.val   =   0.4
            Trusedist_min.val   =   0.001   # smaller re-usedist.
            Taa_samples1.val    =   2
            Taa_samples2.val    =   4
            Taa_thold.val       =   0.07
            Taa_jitter.val      =   0.5
            # cache settings (off)
            Tcache_switch.val   =   0
        elif Trender_preset.val == 8:
            # Slow and precise radiosity & caustics
            Tradiosity.val      =   1
            Tcaustics.val       =   1
            Ttrace_depth.val    =   6
            Tradio_depth.val    =   6
            Tradio_samples.val  =   5000
            Tphoton_count.val   =   1000000
            Tpcluster_d.val     =   2500
            Tpcluster_c.val     =   250
            Tdisp_switch.val    =   1
            Tshad_switch.val    =   1
            Tvolm_switch.val    =   1
            Trad_sampling.val   =   1   # Stratified sampling
            Trad_thold.val      =   0.2
            Trusedist_scr.val   =   0.25
            Trusedist_max.val   =   0.4
            Trusedist_min.val   =   0.001   # smaller re-usedist.
            Taa_samples1.val    =   2
            Taa_samples2.val    =   4
            Taa_thold.val       =   0.07
            Taa_jitter.val      =   0.5
            # cache settings (off)
            Tcache_switch.val   =   0
        Blender.Redraw()
    elif evt == evt_shoDOCS:
        doc_path = None
        if Tdocmenu.val==1:
            doc_path = os.path.normpath(os.path.join(LFHOME, 'PM/Docs/ClassDoc.html'))
        elif Tdocmenu.val!=0:   # 0 = (pseudo)title
            # see if the 'LFE_DOCS' directory is there, if not warn the user it is not there
            doc_path = os.path.normpath(os.path.join(LFHOME, 'PM/LFE_DOCS'))
            if os.path.exists(doc_path):
                if Tdocmenu.val==2:
                    doc_path = os.path.normpath(os.path.join(doc_path, 'GeneralInfo.html'))
                elif Tdocmenu.val==3:
                    doc_path = os.path.normpath(os.path.join(doc_path, 'script.html'))
                elif Tdocmenu.val==4:
                    doc_path = os.path.normpath(os.path.join(doc_path, 'BFILE_IMPORT.txt'))
                elif Tdocmenu.val==5:
                    doc_path = os.path.normpath(os.path.join(doc_path, 'MSPtutorial.html'))
            else:
                print "You did not copy the 'LFE_DOCS' directory to the Lightflow/PM directory !!!"
                EXPORT_FAILED = 4   # not an export failure of course, but just used here as a warning signal
                doc_path = None
        # reset menu
        Tdocmenu.val = 0
        # Open the html document
        if doc_path:
            # catch exception in case for some reason page cannot be opened
            try:
                
                BROWSER_OPEN(doc_path)
                EXPORT_FAILED = 0   # reset in case it was set before
            except:
                ShowError()
                EXPORT_FAILED = 4   # see above
    elif evt == evt_redefpref:
        # Restart the path GUI
        PREF_CANCEL = 1
        PATH_OK = [0, "User redefine request"]
        Draw.Register(pt_draw, main_event, pt_bevent)
    elif evt == evt_imgsize:
        pf = Timsi_percent.val * 0.01
        if Timsi_pref.val==0:
            # 4:3 -> 640 X 480
            Timsi_CustX.val = pf * 640.0
            Timsi_CustY.val = pf * 480.0
        elif Timsi_pref.val==1:
            # 16:9 -> 640 X 360
            Timsi_CustX.val = pf * 640.0
            Timsi_CustY.val = pf * 360.0
        elif Timsi_pref.val==3:
            # From Blender, does not happen for Blender versions > 2.23
            ds = Blender210.getDisplaySettings()
            Timsi_CustX.val = pf * ds.xResolution
            Timsi_CustY.val = pf * ds.yResolution
    elif evt == evt_TGredraw:
        Blender.Redraw()

# FILE SELECT FOR WORLD_TEXTURE
def FileSelect_TEX():
    FSEL.activate(callback_TEX)

def callback_TEX():
    global TWORLD_TEX
    TWORLD_TEX.val = FSEL.filename
    Draw.Register(main_draw, main_event, main_bevent)


####################################
# GUI TO SET THE LAYERS FOR EXPORT #
####################################

def LY_draw():
    global Tlayer_switch

    # get the window coordinate multiply factors
    midx, mulx, muly = GetWindowFactors()

    # clear screen
    BGL.glClearColor(0.5, 0.5, 0.5, 1)
    BGL.glClear(BGL.GL_COLOR_BUFFER_BIT)

    BGL.glColor3f(1,1,1)
    BGL.glRasterPos2i(10*mulx, 490*muly)
    Draw.Text("LAYERS TO EXPORT")

    # width and height of all layer buttons
    wd, ht = 35*mulx, 18*muly

    # Display all layer buttons
    # layers 1-10
    y = 460*muly
    for i in range(0, 10):
        st = "%02d" % (i+1)
        Tlayer_switch[i] = Draw.Toggle(st, evt_ignore, 10*mulx + (i*wd), y, wd, ht, Tlayer_switch[i].val)

    # layers 11-20
    y = 460*muly-ht
    for i in range(10, 20):
        st = "%02d" % (i+1)
        Tlayer_switch[i] = Draw.Toggle(st, evt_ignore, 10*mulx + ((i-10)*wd), y, wd, ht, Tlayer_switch[i].val)

    # All buttons off
    Draw.Button("All Off", evt_alloff, 10*mulx, 330*muly, 150*mulx, ht, "Set all Layer buttons to off")

    # All buttons on
    Draw.Button("All On", evt_allon, 170*mulx, 330*muly, 150*mulx, ht, "Set all Layer buttons to on")

    # Message when trying to return to settings screen with all layer buttons off
    if LAYER_ERR:
        BGL.glColor3f(0, 0, 0)
        BGL.glRecti(10*mulx, 59*muly, 380*mulx, 39*muly)
        BGL.glColor3f(1, 0.5, 0)
        BGL.glRasterPos2i(15*mulx, 45*muly)
        Draw.Text("YOU HAVE TO ENABLE AT LEAST ONE LAYER !")

    # return to settings screen
    Draw.Button("Settings", evt_settscr, 5*mulx, 10*muly, 105*mulx, 20*muly, "Switch to settings screen")


def LY_bevent(evt):
    global Tlayer_switch, Tlayer, LAYER_ERR
    if evt == evt_settscr:
        # Create layer bitmask from switches
        # AND check that at least one layer button is enabled
        bmask = LYOK = 0
        for i in range(20):
            LYOK |= Tlayer_switch[i].val
            if Tlayer_switch[i].val: bmask |= (1 << i)
        if not LYOK:
            LAYER_ERR = 1
            Blender.Redraw()
            return
        LAYER_ERR = 0
        Tlayer.val = bmask
        Draw.Register(main_draw, main_event, main_bevent)
    elif evt == evt_alloff:
        for i in range(20):
            Tlayer_switch[i].val = 0
        Blender.Redraw()
    elif evt == evt_allon:
        for i in range(20):
            Tlayer_switch[i].val = 1
        Blender.Redraw()


#############################################
# GUI TO SET EXTRA RENDER ENGINE PARAMETERS #
#############################################

def mp_draw():
    # default engine
    global Tdisp_switch, Tshad_switch, Tvolm_switch
    global Trad_sampling, Trad_thold, Trusedist_scr, Trusedist_max, Trusedist_min
    global Tlight_accur, Tlight_count, Tlight_depth, Tlight_thold
    global Trad_glas, Trad_metl
    global TCPU
    global Tcache_switch, Tcache_size, Tcache_cells, Tcache_minrad, Tcache_maxrad
    global Tvolum_toggle, Tvolum_sampling, Tvolum_denscach
    global Tsmap_zbuf, Tsmap_samples, Tsmap_bias
    global Trblur_samples

    # clear screen
    BGL.glClearColor(0.5, 0.6, 0.5, 1)
    BGL.glClear(BGL.GL_COLOR_BUFFER_BIT)
    
    # get the window coordinate multiply factors
    midx, mulx, muly = GetWindowFactors()

    # all buttons same width and height, same start x-coord
    wd, ht, st = 125*mulx, 18*muly, 10*mulx

    BGL.glColor3f(0, 0, 0)
    BGL.glRasterPos2i(st, 490*muly)
    Draw.Text("OPTION SWITCHES")
    Tdisp_switch    =   Draw.Toggle("DISPLACEMENT: "+TGSTATE[Tdisp_switch.val], evt_TGredraw, st, 470*muly, wd, ht, Tdisp_switch.val, "Enable/Disable Displacement Mapping")    
    Tshad_switch    =   Draw.Toggle("SHADOWS: "+TGSTATE[Tshad_switch.val], evt_TGredraw, st+wd, 470*muly, wd, ht, Tshad_switch.val, "Enable/Disable Shadows")   
    Tvolm_switch    =   Draw.Toggle("VOLUMETRICS: "+TGSTATE[Tvolm_switch.val], evt_TGredraw, st+2*wd, 470*muly, wd, ht, Tvolm_switch.val, "Enable/Disable Volumetric Rendering")

    BGL.glRasterPos2i(st, 440*muly)
    Draw.Text("RADIOSITY PARAMETERS")
    Trad_sampling   =   Draw.Toggle("Stratified Smp: "+TGSTATE[Trad_sampling.val], evt_TGredraw, st, 420*muly, wd, ht, Trad_sampling.val, "Enable/Disable Stratified Sampling")
    Trad_thold      =   Draw.Number("Threshold: ", evt_ignore, st+wd, 420*muly, wd, ht, Trad_thold.val, 0.0, 1.0,
                                "Maximum error allowed in calculations (percentage)")
    Trusedist_scr   =   Draw.Number("RUD screen: ", evt_ignore, st, 400*muly, wd, ht, Trusedist_scr.val, 0.0, 1.0,
                                "Screen re-use-distance")
    Trusedist_max   =   Draw.Number("RUD maximum: ", evt_ignore, st+wd, 400*muly, wd, ht, Trusedist_max.val, 0.0, 1.0,
                                "Maximum re-use-distance")
    Trusedist_min   =   Draw.Number("RUD minimum: ", evt_ignore, st+2*wd, 400*muly, wd, ht, Trusedist_min.val, 0.0, 1.0,
                                "Minimum re-use-distance")

    BGL.glRasterPos2i(st, 370*muly)
    Draw.Text("LIGHTING PARAMETERS")
    Tlight_accur    =   Draw.Number("Accuracy: ", evt_ignore, st, 350*muly, wd, ht, Tlight_accur.val, 0.0, 1.0,
                                "Lighting accuracy (percentage)")
    Tlight_thold    =   Draw.Number("Threshold: ", evt_ignore, st+wd, 350*muly, wd, ht, Tlight_thold.val, 0.0, 1.0,
                                "Maximum allowed error of shadow computation")
    Tlight_count    =   Draw.Number("Count: ", evt_ignore, st, 330*muly, wd, ht, Tlight_count.val, 1, 10,
                                "Number of lights involved per shading location")
    Tlight_depth    =   Draw.Number("Depth: ", evt_ignore, st+wd, 330*muly, wd, ht, Tlight_depth.val, 1, 16,
                                "Maximum tracing depth with correct lighting")

    BGL.glRasterPos2i(st, 302*muly)
    Draw.Text("RADIOSITY CALCULATION FOR _GLAS & _METL MATERIALS")
    Trad_glas       =   Draw.Toggle("GLASS: "+TGSTATE[Trad_glas.val], evt_TGredraw, st, 280*muly, wd, ht, Trad_glas.val, "Enable/Disable")
    Trad_metl       =   Draw.Toggle("METAL: "+TGSTATE[Trad_metl.val], evt_TGredraw, st+wd, 280*muly, wd, ht, Trad_metl.val, "Enable/Disable")

    BGL.glRasterPos2i(st, 250*muly)
    Draw.Text("CACHING PARAMETERS")
    Tcache_switch   =   Draw.Toggle("CACHING: "+TGSTATE[Tcache_switch.val], evt_TGredraw, st, 230*muly, wd, ht, Tcache_switch.val, "Enable/Disable Caching")
    Tcache_size     =   Draw.Number("Size: ", evt_ignore, st, 210*muly, wd, ht, Tcache_size.val, 10, 10000, "Number of cell clusters")
    Tcache_cells    =   Draw.Number("Cells: ", evt_ignore, st+wd, 210*muly, wd, ht, Tcache_cells.val, 10, 10000, "Number of cells in each cluster")
    Tcache_minrad   =   Draw.Number("Radius Min: ", evt_ignore, st, 190*muly, wd, ht, Tcache_minrad.val, 0.0, 10.0, "Sample minimum distance")
    Tcache_maxrad   =   Draw.Number("Radius Max: ", evt_ignore, st+wd, 190*muly, wd, ht, Tcache_maxrad.val, 0.0, 10.0, "Sample maximum distance")

    BGL.glRasterPos2i(st+2.0*wd, 250*muly)
    Draw.Text("PROCESSORS")
    # minimum & default 1, maximum: 16 --- Enough, anyone actually can use that???
    TCPU        =   Draw.Number("Num.CPU: ", evt_ignore, st+2.0*wd, 230*muly, wd, ht, TCPU.val, 1, 16, "Number of CPU's used (multiprocessor systems)")

    # VOLUMETRIC FOG OPTIONS, moved from imagers/dof screen
    BGL.glRasterPos2i(st, 160*muly)
    Draw.Text("VOLUMETRIC FOG/SPOT HALO")
    Tvolum_toggle   =   Draw.Toggle("VOLUMETRICS: "+TGSTATE[Tvolum_toggle.val], evt_TGredraw, st, 140*muly, wd, ht, Tvolum_toggle.val, "Enable/Disable real volumetric calculations")
    Tvolum_sampling =   Draw.Number("Sampling: ", evt_ignore, st, 120*muly, wd, ht, Tvolum_sampling.val, 0.01, 100.0,
                                "Sampling interval on viewing ray")
    # 256Mb enough as maximum?
    Tvolum_denscach =   Draw.Number("Density cache: ", evt_ignore, st, 100*muly, wd, ht, Tvolum_denscach.val, 1024, 262144,
                                "Number of samples on unit viewing ray")

    # REFRACTION/REFLECTION BLUR AMOUNT
    BGL.glRasterPos2i(st+1.5*wd, 160*muly)
    Draw.Text("REFRACTION/REFLECTION BLUR")
    Trblur_samples  =   Draw.Number("Samples: ", evt_ignore, st+1.5*wd, 140*muly, wd, ht, Trblur_samples.val, 1, 100, "Number of blur samples")

    # SHADOWMAP PARAMETERS
    BGL.glRasterPos2i(st, 70*muly)
    Draw.Text("SHADOWMAP PARAMETERS")
    Tsmap_zbuf      =   Draw.Number("BufSize: ", evt_ignore, st, 50*muly, wd, ht, Tsmap_zbuf.val, 64, 2048, "ZBuffer size")
    Tsmap_samples   =   Draw.Number("Samples: ", evt_ignore, st+wd, 50*muly, wd, ht, Tsmap_samples.val, 1, 100, "Number of shadowmap samples")
    Tsmap_bias      =   Draw.Number("Bias: ", evt_ignore, st+2*wd, 50*muly, wd, ht, Tsmap_bias.val, 0.01, 5.0, "Bias value, don't modify unless really necessary!")

    # return to settings screen
    Draw.Button("Settings", evt_settscr, 5*mulx, 10*muly, 105*mulx, 20*muly, "Switch to settings screen")


def mp_bevent(evt):
    if evt == evt_settscr:
        Draw.Register(main_draw, main_event, main_bevent)
    elif evt == evt_TGredraw:
        Blender.Redraw()


###########################################
# THE IMAGERS/DOF GUI                     #
###########################################

def xtr_draw():
    global Tdof_method, Tdof_radius, Tdof_mask, Tdof_autofocus, Tdof_aperture
    global Thalo_toggle, Thalo_lens_kr, Thalo_lens_km, Thalo_lens_sh
    global Tglit_toggle, Tglit_radius, Tglit_intens, Tglit_thold
    global Tfilm_toggle, Tfilm_grain

    # clear screen
    BGL.glClearColor(0.5, 0.5, 0.5, 1)
    BGL.glClear(BGL.GL_COLOR_BUFFER_BIT)
    
    # get the window coordinate multiply factors
    midx, mulx, muly = GetWindowFactors()

    # all buttons same width and height, same start x-coord
    wd, ht, st = 125*mulx, 18*muly, 10*mulx

    # DOF OPTION BUTTONS
    BGL.glColor3f(0,0,0)
    BGL.glRasterPos2i(st, 490*muly)
    Draw.Text("DEPTH OF FIELD OPTIONS")
    Tdof_method     =   Draw.Toggle("REAL DOF: "+TGSTATE[Tdof_method.val], evt_TGredraw, st, 470*muly, wd, ht, Tdof_method.val, "Calculate real DoF")
    if not Tdof_method.val:
        # fake DoF options
        Tdof_radius     =   Draw.Number("Radius: ", evt_ignore, st, 450*muly, wd, ht, Tdof_radius.val, 0.0, 1.0,
                                    "Blur radius")
        Tdof_mask       =   Draw.Number("Mask: ", evt_ignore, wd+st, 450*muly, wd, ht, Tdof_mask.val, 1, 100,
                                    "Blur mask in pixels")
        Tdof_autofocus  =   Draw.Toggle("AutoFocus: "+TGSTATE[Tdof_autofocus.val], evt_TGredraw, 2.0*wd+st, 450*muly, wd, ht, Tdof_autofocus.val,
                                    "Enable/Disable Autofocus")
    else:
        # real DoF options
        Tdof_aperture   =   Draw.Number("Aperture: ", evt_ignore, st, 450*muly, wd, ht, Tdof_aperture.val, 0.0, 10.0,
                                    "Aperture of camera lens, 0.0 = perfect focus")

    # HALO IMAGER BUTTONS
    BGL.glRasterPos2i(st, 420*muly)
    Draw.Text("HALO IMAGER OPTIONS")
    Thalo_toggle    =   Draw.Toggle("HALO: "+TGSTATE[Thalo_toggle.val], evt_halomutex, st, 400*muly, wd, ht, Thalo_toggle.val, "Enable/Disable Halo Imager")
    Thalo_lens_kr   =   Draw.Number("Reflection: ", evt_ignore, 10*mulx, 380*muly, wd, ht, Thalo_lens_kr.val, 0.0, 1.0,
                                "Reflection factor of camera lens")
    Thalo_lens_km   =   Draw.Number("Smoothness: ", evt_ignore, wd+st, 380*muly, wd, ht, Thalo_lens_km.val, 0.0, 1.0,
                                "Smoothness, the greater, the larger the halos")
    Thalo_lens_sh   =   Draw.Number("Shinyness: ", evt_ignore, 2.0*wd+st, 380*muly, wd, ht, Thalo_lens_sh.val, 0.0, 1.0,
                                "Shinyness, the greater, the stronger the halos")

    # GLITTER IMAGER BUTTONS
    BGL.glRasterPos2i(st, 350*muly)
    Draw.Text("GLITTER IMAGER OPTIONS")
    Tglit_toggle    =   Draw.Toggle("GLITTER: "+TGSTATE[Tglit_toggle.val], evt_glitmutex, st, 330*muly, wd, ht, Tglit_toggle.val, "Enable/Disable Glitter Imager")
    Tglit_radius    =   Draw.Number("Radius: ", evt_ignore, st, 310*muly, wd, ht, Tglit_radius.val, 0.0, 100.0,
                                "Radius of glitters")
    Tglit_intens    =   Draw.Number("Intensity: ", evt_ignore, wd+st, 310*muly, wd, ht, Tglit_intens.val, 0.0, 1.0,
                                "Intensity of glitters")
    Tglit_thold     =   Draw.Number("Threshold: ", evt_ignore, 2.0*wd+st, 310*muly, wd, ht, Tglit_thold.val, 0.0, 100.0,
                                "Threshold above which a color produces glittering")

    # FILM IMAGER OPTIONS, the only one that can have any of the other imagers as an extra imager
    BGL.glRasterPos2i(st, 280*muly)
    Draw.Text("FILM IMAGER OPTIONS")
    Tfilm_toggle    =   Draw.Toggle("FILM: "+TGSTATE[Tfilm_toggle.val], evt_TGredraw, st, 260*muly, wd, ht, Tfilm_toggle.val, "Enable/Disable Film Imager")
    Tfilm_grain     =   Draw.Number("Grain: ", evt_ignore, st, 240*muly, wd, ht, Tfilm_grain.val, 0.0, 1.0,
                                "Graininess of the film")

    # WARN USER FOR MUT.EXC. OF FAKE DOF, HALO & GLITTER
    BGL.glRecti(st, 135*muly, mulx*85, 155*muly)
    BGL.glColor3f(1.0, 0.5, 0)
    BGL.glRasterPos2i(15*mulx, 140*muly)
    Draw.Text("WARNING!")
    BGL.glColor3f(1, 1, 0)
    BGL.glRasterPos2i(st, 120*muly)
    Draw.Text("Fake DoF, Halo & Glitter cannot be used at the same time!")
    BGL.glRasterPos2i(st, 100*muly)
    Draw.Text("Enabling one will disable the others.")
    BGL.glRasterPos2i(st, 80*muly)
    Draw.Text("DoF will revert to 'REAL' when enabling Halo or Glitter.")
    BGL.glRasterPos2i(st, 60*muly)
    Draw.Text("Which does not mean DoF will be enabled, only when aperture")
    BGL.glRasterPos2i(st, 40*muly)
    Draw.Text("is not zero will it actually be calculated.")

    Draw.Button("Settings", evt_settscr, 5*mulx, 10*muly, 105*mulx, 20*muly, "Switch to settings screen")


def xtr_bevent(evt):
    global Thalo_toggle, Tglit_toggle
    if evt == evt_settscr:
        Draw.Register(main_draw, main_event, main_bevent)
    elif evt == evt_dofmet:
        # fake DoF can't be used with glitter or halo
        if Tdof_method.val==0:
            Tglit_toggle.val = 0
            Thalo_toggle.val = 0
        Blender.Redraw()
    elif evt == evt_halomutex:
        # halo can't be used with glitter or fake DoF
        Tdof_method.val = 1
        Tglit_toggle.val = 0
        Blender.Redraw()
    elif evt == evt_glitmutex:
        # glitter can't be used with halo of fake DoF
        Tdof_method.val = 1
        Thalo_toggle.val = 0
        Blender.Redraw()
    elif evt == evt_TGredraw:
        Blender.Redraw()


###########################################
# THE RENDER GUI                          #
###########################################

################################### TARGA IMAGE LOADER (UNCOMPRESSED TRUECOLOR ONLY) #####################################################
# based partly on code by Jean-Michel Soler, although quite modified now

# pointed out by "hannibar", "TGA file not found" and other messages might be confused with texture errors, removed

# Loads uncompressed Targa files and creates OGL Buffer for display
# Uses array module, if available.
# Just in case for linux the array module is not installed by default like it was on my system,
# use an alternate system to load tga in 1Mb chunks
# can be very much slower for large files, might even crash with MemoryError on some systems,
# maybe my Linux Python2.0 install was an exception, hopefully everybody else has access to the array module
def LoadRawTGA():
    global TGA
    TGA = None
    # better use full path
    # if this is an animation, the image is in imgdir
    if Tanimation.val:
        # Animation targa's are in the format frame_xxx.tga
        cframe = Blender.Get('curframe')
        imgpath = os.path.join(imgdir, ('frame_%04d.tga' % cframe))
    else:
        imgpath = os.path.join(outdir, frame_outname+'.tga')
    try:
        
        tf = open(imgpath, 'rb')
    except IOError:
        # No TGA file found, nothing there (yet)...
        return
    else:
        try:
            
            # read header
            tga = tf.read(18)
            # only can handle Uncompressed True-Color format
            # if it isn't, raise error
            img_type = unpack("B", tga[2])[0]
            if img_type!=2:
                raise Exception("Unsupported Targa image format!")
            wd, ht = unpack('H', tga[12:14])[0], unpack('H', tga[14:16])[0]
            bits = unpack("B", tga[16])[0]
            # calculate the software image read offset, targa could contain an alpha channel
            img_inc = (bits>>3)
            # determine OGL data format from number of bytes
            dformat = DISPLAY_MODES[img_inc]
            # in case of an ID, read past it
            idlen = unpack('B', tga[0])[0]
            if idlen: tga = tf.read(idlen)
            if ARMOD:
                # read all remaining data at once AS A BYTE ARRAY, unpack from structmod can fail (MemoryError) with huge strings
                total_pixels = wd * ht
                total_bytes = total_pixels * img_inc
                tga = array.array('B')
                tga.fromfile(tf, total_bytes)
            else:
                # no array module, just read all remaining data
                tga = tf.read()
                tf.close()
                total_pixels = wd * ht
                total_bytes = total_pixels * img_inc
        except:
            # better write a 'friendly' error
            if PRINT_TRACE:
                ShowError()
                print "\nError trying to read TGA file, ignore, nothing serious!\n"
            if not tf.closed: tf.close()
            return
        # create OpenGL pixel buffer
        GLbuf = BGL.Buffer(BGL.GL_BYTE, total_bytes)
        if fast_display_ok:
            # let OGL handle RGB(A)<->BGR(A)
            if ARMOD:
                # clean and fast, just assign
                GLbuf[:] = tga
            else:
                # 'manual' unpack in maximum of 1MB chunks, there seems to be a limit to the unpack string
                chunks, scraps = total_bytes >> 20, total_bytes & 0xfffff
                ch_ofs = 0
                if chunks:
                    for ch in range(chunks):
                        GLbuf[ch_ofs:ch_ofs+0x100000] = unpack("1048576B", tga[ch_ofs:ch_ofs+0x100000])
                        ch_ofs += 0x100000
                # and the remaining scraps...
                GLbuf[ch_ofs:total_bytes] = unpack(("%dB" % scraps), tga[ch_ofs:total_bytes])
        else:
            # We have to do convert ourselves, slower, but not as much as you would expect
            # swap R & B and copy to OGL Buffer, ignores alpha, not used
            img_ofs = 0
            if ARMOD:
                # array module, no unpacking needed
                for p in range(total_pixels):
                    GLbuf[img_ofs], GLbuf[img_ofs+1], GLbuf[img_ofs+2] = tga[img_ofs+2], tga[img_ofs+1], tga[img_ofs]
                    img_ofs += img_inc
            else:
                # have to unpack too...
                for p in range(total_pixels):
                    dt = unpack('3B', tga[img_ofs:img_ofs+3])
                    # swap R & B and write in OGL Buffer
                    GLbuf[img_ofs], GLbuf[img_ofs+1], GLbuf[img_ofs+2] = dt[2], dt[1], dt[0]
                    img_ofs += img_inc
        TGA = (wd, ht, GLbuf, dformat)


###############################################################################################################################
def getBGC():
    #avocado 0.25, 0.4, 0.4, 1
    #tomato  0.4, 0.25, 0.25, 1
    return BGL.glClearColor(0.25, 0.4, 0.4, 1)
def rd_draw():
    global RENDER_STARTED, Tautodisp_toggle, Tautodisp_interv
    
    #BGL.glClearColor(0.5, 0.25, 0.25, 1)
    getBGC()
    BGL.glClear(BGL.GL_COLOR_BUFFER_BIT)

    midx, mulx, muly = GetWindowFactors()

    if Tanimation.val==1:
        # also display frame number
        st = "CURRENT FRAME: %d" % Blender.Get('curframe')
    else:
        st = "CURRENT RENDER"
    BGL.glColor3f(1, 1, 1)
    #BGL.glRasterPos2i(midx - len(st)*4, 490*muly)
    BGL.glRasterPos2i(5*mulx, 490*muly)
    Draw.Text(st)

    # render window, based on 380x285 (4:3), but changing window size
    # will also alter this, code will adapt to it.
    wsize = (380*mulx, 285*muly)
    border = 1
    ib = 1.0/border
    # window coordinates
    wcrd = (5*mulx, 190*muly, 5*mulx+wsize[0], 190*muly+wsize[1])

    # 3d window background
    BGL.glColor3f(0.5, 0.5, 0.5)
    BGL.glRectf(wcrd[0]-ib*border, wcrd[1]-border, wcrd[2]+border, wcrd[3]+ib*border)

    BGL.glColor3f(1,1,1)
    BGL.glRectf(wcrd[0]+ib*border, wcrd[1]-border, wcrd[2]+border, wcrd[3]-ib*border)

    BGL.glColor3f(0,0,0)
    apply(BGL.glRectf, wcrd)

    if TGA:
        # window aspect ratio to make it fit in window without distortion
        if TGA[0] > TGA[1]:
            aspr = wsize[0] / float(TGA[0])
            a1, a2 = TGA[0]/float(TGA[1]), wsize[0]/float(wsize[1])
        else:
            aspr = wsize[1] / float(TGA[1])
            a1, a2 = TGA[1]/float(TGA[0]), wsize[1]/float(wsize[0])
        if a2 > a1:
            a2 = a1/a2
        else:
            a2 = 1.0
        # center it in window
        BGL.glRasterPos2f(wcrd[0] + (wsize[0] - TGA[0]*aspr*a2) * 0.5, wcrd[1] + (TGA[1]*aspr*a2 + wsize[1]) * 0.5)
        # Targa is upside down, negative y-scale
        BGL.glPixelZoom(aspr*a2, -aspr*a2)
        BGL.glPixelStorei(BGL.GL_UNPACK_ALIGNMENT, 1)   # important!!!, crash otherwise with odd width/height
        BGL.glDrawPixels(TGA[0], TGA[1], TGA[3], BGL.GL_UNSIGNED_BYTE, TGA[2])

    if not Tanimation.val:  # single frame
        # Lightflow start button
        if RENDER_STARTED!=1:
            # don't display when it is already started
            Draw.Button("START RENDER", evt_STARTLF, 150*mulx, 150*muly, 100*mulx, 20*muly, "Start Lightflow :o)")
            # Autodisplay might not be possible on Linux
            if AUTODISP_OK:
                Tautodisp_toggle = Draw.Toggle("AutoDisplay: "+TGSTATE[Tautodisp_toggle.val], evt_TGredraw, 10*mulx, 120*muly, 185*mulx, 20*muly,
                                    Tautodisp_toggle.val, "Enable/Disable automatic display while rendering")
                Tautodisp_interv = Draw.Number("Display interval: ", evt_ignore, 200*mulx, 120*muly, 185*mulx, 20*muly, Tautodisp_interv.val,
                                    1.0, 60.0, "Time in seconds to wait for display refresh")
        if not Tautodisp_toggle.val:
            Draw.Button("CLICK HERE TO DISPLAY OR PRESS R-KEY", evt_display, 5*mulx, 60*muly, 380*mulx, 20*muly, "Reload and display targa")
    else:   # full animation
        if not ANIM_STARTED:
            # can only display when not exporting/rendering
            Draw.Button("EXPORT/RENDER ANIM", evt_eranim, 75*mulx, 150*muly, 250*mulx, 20*muly, "Export/Render complete animation")
            # arrow keys message
            BGL.glColor3f(1, 1, 0)
            BGL.glRasterPos2i(5*mulx, 130*muly)
            Draw.Text('Use left/right arrow keys to advance frames (continuous).')
            BGL.glRasterPos2i(5*mulx, 110*muly)
            Draw.Text('Use numpad 4 & 6 to step frame by frame')
        else:
            # animation export/render started, display message how to abort rendering...
            BGL.glColor3f(0.0, 1, 0.5)
            BGL.glRasterPos2i(5*mulx, 110*muly)
            Draw.Text('To stop Export & render, click in the DOS-console/terminal,')
            BGL.glRasterPos2i(5*mulx, 90*muly)
            Draw.Text('then use the CTRL-C key combination.')

    if RENDER_STARTED:
        BGL.glColor3f(0.0, 1, 0.5)
        BGL.glRasterPos2i(80*mulx, 160*muly)
        if sys.platform=='win32':
            Draw.Text('Use CTRL-C in DOS console to stop rendering.')
        else:
            Draw.Text('Use CTRL-C in terminal to stop rendering.')

    if RENDER_STARTED and Tautodisp_toggle.val:
        if sys.platform=='win32':
            st = 'Use any other key in DOS console to stop autodisplay'
        else:
            st = 'Press enter-key in terminal to stop autodisplay'
        BGL.glColor3f(0.0, 1, 0.5)
        BGL.glRasterPos2i(5*mulx, 90*muly)
        Draw.Text(st)

    # display status
    BGL.glColor3f(0, 0, 0)
    BGL.glRecti(5*mulx, 35*muly, 385*mulx, 55*muly)
    if RENDER_STARTED==-1:  # LF FAILED!
        BGL.glColor3f(1,0,0)
    else:
        BGL.glColor3f(1, 1, 0)
    BGL.glRasterPos2i(20*mulx, 40*muly)
    Draw.Text(REND_MSG)

    if not (RENDER_STARTED and Tautodisp_toggle.val) and not ANIM_STARTED:
        # only can handle events when not autodisplaying
        Draw.Button("Settings", evt_settscr, 5*mulx, 10*muly, 105*mulx, 20*muly, "Switch to settings screen")


def rd_event(evt, val):
    global REND_MSG, RENDER_STARTED, CTRLC_USED
    if (evt==Draw.QKEY) and (not val):
        SCRIPT_EXIT()
    if (evt==Draw.RKEY) and (not val):
        REND_MSG, activity = LFRUNNING()
        if activity!=1:
            # py/lf finished/terminated
            CTRLC_USED = 0
            RENDER_STARTED = 0
        # reload and display targa
        LoadRawTGA()
## jms : modif 16/08/2003
        if BL_VERSION<228:   
            Blender.Window.Redraw(Blender.Window.Const.TEXT)
        else:
            Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003
        """
        Blender.Window.Redraw(Blender.Window.Const.TEXT)
        """

    # if animition render, using left and right cursor keys will advance frames
    if (Tanimation.val==1):
        # left/right cursor keys to advance frames from animation
        frset = (Blender.Get('staframe'), Blender.Get('endframe'))  # current start/end frame
        if (evt==Draw.LEFTARROWKEY) or ((evt==Draw.PAD4) and (not val)):
            # decrease curframe and update image (if possible)
            cframe = Blender.Get('curframe') - 1
            # wrap to frame settings
            if cframe<frset[0]:
                cframe = frset[1]
            elif cframe>frset[1]:
                cframe = frset[0]
            # set the new frame
            if BL_VERSION<=223 or BL_VERSION>=228: 
                Blender.Set('curframe', cframe)
            else:
                curscene = Blender.Scene.getCurrent()
                curscene.frameSettings(curscene.startFrame(), curscene.endFrame(), cframe)
            # update display
            REND_MSG, activity = LFRUNNING()
            if activity!=1:
                # py/lf finished/terminated
                CTRLC_USED = 0
                RENDER_STARTED = 0
            # reload and display targa
            LoadRawTGA()

## jms : modif 16/08/2003
            if BL_VERSION<228:   
               Blender.Window.Redraw(Blender.Window.Const.TEXT)
            else:
               Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003
            """
            Blender.Window.Redraw(Blender.Window.Const.TEXT)
            """

        if (evt==Draw.RIGHTARROWKEY) or ((evt==Draw.PAD6) and (not val)):
            # increase curframe and update image (if possible)
            cframe = Blender.Get('curframe') + 1
            # wrap to frame settings
            if cframe<frset[0]:
                cframe = frset[1]
            elif cframe>frset[1]:
                cframe = frset[0]
            # set the new frame
            if BL_VERSION<=223 or BL_VERSION>=228:
                Blender.Set('curframe', cframe)
            else:
                curscene = Blender.Scene.getCurrent()
                curscene.frameSettings(curscene.startFrame(), curscene.endFrame(), cframe)
            # update display
            REND_MSG, activity = LFRUNNING()
            if activity!=1:
                # py/lf finished/terminated
                CTRLC_USED = 0
                RENDER_STARTED = 0
            # reload and display targa
            LoadRawTGA()
## jms : modif 16/08/2003
            if BL_VERSION<228:   
               Blender.Window.Redraw(Blender.Window.Const.TEXT)
            else:
               Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003
            """
            Blender.Window.Redraw(Blender.Window.Const.TEXT)
            """ 

def StartLightflow(wait=0):
    global LFPID
    # Start Lightflow with the last saved .py file
    LFPID = None
    if wait:
        waitval = os.P_WAIT
    else:
        waitval = os.P_NOWAIT
    GetOutdir()
    # os.chdir(outdir) not needed anymore, now uses fullpaths everywhere
    if sys.platform=='win32':
        # Prevent "import site failed" error, by not using it (-S switch)
        # Of course it will still happen when a 1.5 script is run outside of Blender
        # Not really relevant anymore, but just in case somebody still wants to use Python 1.5...
        args = [' -S ' + pyfilepath]
        # WIN32: LFPID IS NOT PROCESS ID, IT IS ACTUALLY THE PROCESS HANDLE
        LFPID = os.spawnv(waitval, Tpy_execpath.val, args)
    else:
        # Linux Lightflow can use any python version (see START())
        args = (Tpy_execpath.val, pyfilepath)
        LFPID = os.spawnv(waitval, Tpy_execpath.val, args)


def LFRUNNING():
    # DETERMINE IF LIGHTFLOW IS STILL RUNNING
    # uses extension module for win32
    # returns message and activity flag
    RUNNING = 0
    if LFPID==-1:
        # start of script, LFPID not available yet, can't tell if running
        return "Ready!", 1
    if (sys.platform=='win32'):
        # will fail if win32procinfo was not imported, in which case return activity flag as if it was running
        try:
            
            cd = win32procinfo.getStatus_PH(LFPID)  # !!!!!! PROCESS HANDLE, NOT PID (see StartLightflow) !!!!!
        except:
            return "CAN'T DETERMINE PYTHON/LIGHTFLOW ACTIVITY", 1
        else:
            RUNNING = (cd==259) # STILL_ACTIVE
            if RUNNING:
                string = 'LIGHTFLOW STILL WORKING...'
                RUNNING = 1
            elif cd==0:
                string = 'LIGHTFLOW DONE.'
                RUNNING = 0
            else:
                if CTRLC_USED:
                    string = 'CTRL-C was used, Python/Lightflow terminated!'
                else:
                    string = 'PYTHON/LIGHTFLOW FAILED !!!'
                RUNNING = -1
    else:
        try:
            RUNNING = os.waitpid(LFPID, os.WNOHANG)
        except:
            RUNNING = (1, 0)
        if RUNNING[0]==0:
            string = 'LIGHTFLOW STILL WORKING...'
            # return one value like win32
            RUNNING = 1
        elif RUNNING[1]==0:
            string = 'LIGHTFLOW DONE.'
            RUNNING = 0
        else:
            if CTRLC_USED:
                string = 'CTRL-C was used, Python/Lightflow terminated!'
            else:
                string = 'PYTHON/LIGHTFLOW FAILED !!!'
            RUNNING = -1
    return string, RUNNING


# Prints out any errors, the same way as normally happens, but without stopping the script, used everywhere
# Now possible to only print the error message, which probably is more helpful to users,
# all the python error stuff might confuse
def ShowError():
    print "EXCEPTION OCCURED:"
    if PRINT_TRACE:
        traceback.print_exc(file=sys.stdout)
    else:
        print sys.exc_info()[0]


# SIGNAL HANDLER TO CATCH KEYBOARD INTERRUPTS
# needed since LFArender can stop at any time using CTRL-C,
# this will pass KeyboardInterrupt to the script too at any point where it can't be catched (or ?)
# Here it will not raise KeyboardInterrupt or any other error, to make sure that the script continues.
def CTRLC_handler(signum, frame):
    global CTRLC_USED
    CTRLC_USED = 1
    print "Ctrl-C was used"


def rd_bevent(evt):
    global file, meshfile, matfile
    global RENDER_STARTED, REND_MSG, ANIM_STARTED, LFPID, CTRLC_USED
    # image resolution
    global Timsi_CustX, Timsi_CustY
    if evt == evt_settscr:
        # back to settings GUI
        # reset the rendering flag
        RENDER_STARTED = 0
        REND_MSG = 'Ready!'
        Draw.Register(main_draw, main_event, main_bevent)
    elif evt == evt_TGredraw:
        Blender.Redraw()
    elif evt == evt_STARTLF:
        # Don't start Lightflow again if it already was started
        # A python file nust exist
        GetOutdir()
        if not os.path.exists(pyfilepath):
            RENDER_STARTED = 0
            REND_MSG = 'NO PYTHON FILE FOUND!'
        elif RENDER_STARTED:
            # Don't re-run if it is still active
            REND_MSG, activity = LFRUNNING()
            if activity==1:
                RENDER_STARTED = 1
                REND_MSG = 'LIGHTFLOW IS ACTIVE, NOT RESTARTED'
        else:
            # must use sigint handler, the script can be stopped without it,
            # Keyboard interrupt is passed without being able to catch it
            CTRLC_USED = 0
            StartLightflow()
            RENDER_STARTED = 1
            REND_MSG = 'LIGHTFLOW STARTED IN BACKGROUND'
            # autodisplay might not be possible on Linux
            if AUTODISP_OK and Tautodisp_toggle.val:
                # clear both std-in/-out just in case
                sys.stdout.flush()
                sys.stdin.flush()
                keyhit = 0
                try:
                    while RENDER_STARTED:
                        # KILL BUTTON IS USELESS WITH LFP2Arender, only kills LFp2a, not lightflow
                        # kill happens automatically when ctrl-c is pressed, so catch keyboard interrupt
                        keyhit = keypressed()
                        if keyhit: break
                        REND_MSG, activity = LFRUNNING()
                        if activity!=1: RENDER_STARTED = 0
                        LoadRawTGA()

## jms : modif 16/08/2003
                        if BL_VERSION<228:   
                              Blender.Window.Redraw(Blender.Window.Const.TEXT)
                        else: 
                              Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003
                        """
                        Blender.Window.Redraw(Blender.Window.Const.TEXT)
                        """    
                        time.sleep(Tautodisp_interv.val)
                except KeyboardInterrupt:
                    ShowError()
                    keyhit = 321
                if keyhit:
                    REND_MSG, activity = LFRUNNING()
                    if activity!=1: RENDER_STARTED = 0
                    LoadRawTGA()
                    if keyhit==321:
                        REND_MSG += ' Render killed (ctrl-c)...'
                    else:
                        REND_MSG += ' Autodisplay stopped...'
                    # reset autodisplay switch
                    Tautodisp_toggle.val = 0

## jms : modif 16/08/2003
        if BL_VERSION<228:   
          Blender.Window.Redraw(Blender.Window.Const.TEXT)
        else: 
          Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003
        """
        Blender.Window.Redraw(Blender.Window.Const.TEXT)
        """
 
    elif evt == evt_display:
        REND_MSG, activity = LFRUNNING()
        if activity!=1:
            # py/lf finished/terminated
            CTRLC_USED = 0
            RENDER_STARTED = 0
        LoadRawTGA()
## jms : modif 16/08/2003
        if BL_VERSION<228:   
                              Blender.Window.Redraw(Blender.Window.Const.TEXT)
        else: 
                              Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003
        """
        Blender.Window.Redraw(Blender.Window.Const.TEXT)
        """

    elif evt == evt_KILL:
        # Terminate Lightflow, but check if it is actually running first
        REND_MSG, activity = LFRUNNING()
        if activity==1:
            if sys.platform=='win32':
                # exception won't happen here since button will not be available if module not loaded
                win32procinfo.kill_PH(LFPID)
            else:
                os.kill(LFPID, 9)   # SIGKILL
            REND_MSG = "Python/Lightflow killed..."
        # Load the last result tga, if possible, and display
        LoadRawTGA()
        RENDER_STARTED = 0
        # write message in the console as well
        print "\n"+REND_MSG

## jms : modif 16/08/2003
        if BL_VERSION<228:   
           Blender.Window.Redraw(Blender.Window.Const.TEXT)
        else: 
           Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003

        """
        Blender.Window.Redraw(Blender.Window.Const.TEXT)
        """

    elif evt == evt_eranim:
        # EXPORT AND RENDER THE COMPLETE ANIMATION
        # Check for KeyboardInterrupt
        # get the image size here again, in case it changed
        if Timsi_pref.val==3:   # no version>223 check necessary, menu item not available there
            ds = Blender210.getDisplaySettings()
            pf = Timsi_percent.val * 0.01
            Timsi_CustX.val = pf * ds.xResolution
            Timsi_CustY.val = pf * ds.yResolution
        cframe = Blender.Get('curframe')
        startframe = Blender.Get('staframe')
        endframe = Blender.Get('endframe')
        if Tautocheck.val==2:
            # Get the selected objects to export
            obs = Blender.Object.GetSelected()
            if (obs==None) or (len(obs)==0):
                # Nothing selected
                REND_MSG = "NO OBJECTS FOR EXPORT SELECTED, NOTHING DONE !"
                RENDER_STARTED = -1
                Blender.Redraw()
                return
            else:
                # convert to name list, and check that there is at least one actual mesh in the list
                selected_obnames = []
                atleast_one_mesh = 0
                for ob in obs:
                    selected_obnames.append(ob.name)
                    if BL_VERSION>223:
                        atleast_one_mesh |= (ob.getType()=='Mesh')
                    else:
                        atleast_one_mesh |= Blender210.isMesh(ob.name)
                if not atleast_one_mesh:
                    REND_MSG = "NO MESHES AMONG SELECTED OBJECTS, NOTHING DONE !"
                    RENDER_STARTED = -1
                    Blender.Redraw()
                    return
        else:
            selected_obnames = None

        ANIM_STARTED = 1

        for currentframe in range(startframe, endframe+1):
            numobs = 0
            try:
                REND_MSG = 'Exporting frame %d' % currentframe
              
## jms : modif 16/08/2003
                if BL_VERSION<228:   
                   Blender.Window.Redraw(Blender.Window.Const.TEXT)
                else: 
                   Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003

                """
                Blender.Window.Redraw(Blender.Window.Const.TEXT)
                """

                # set the new frame
                if BL_VERSION<=223 or BL_VERSION>=228:
                    Blender.Set('curframe', currentframe)
                else:
                    curscene = Blender.Scene.getCurrent()
                    curscene.frameSettings(curscene.startFrame(), curscene.endFrame(), currentframe)

                # RedrawAll() makes the screen flicker, so just refresh text and 3d window separately
                
                
## jms : modif 16/08/2003
                if BL_VERSION<228:   
                     Blender.Window.Redraw(Blender.Window.Const.VIEW3D)
                     Blender.Window.Redraw(Blender.Window.Const.TEXT)
                else: 
                     Blender.Window.Redraw(Blender.Window.Types['VIEW3D'])
                     Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003

                """
                Blender.Window.Redraw(Blender.Window.Const.VIEW3D)
                Blender.Window.Redraw(Blender.Window.Const.TEXT)
                """
 
                # try to export everything
                try:
                    numobs, numlamps = ExportIt(selected_obnames)
                except IOError:
                    # close file, meshfile and/or matfile if open and defined
                    ShowError()
                    try:
                        if not file.closed:
                            print "Python export file write failure"
                            file.close()
                        if not meshfile.closed:
                            print "Meshfile write failure"
                            meshfile.close()
                        if not matfile.closed:
                            print "Materialfile write failure"
                            matfile.close()
                    except:
                        pass
                    # repair progressbar, might be half displayed
                    pbar(1 ,'')
                    REND_MSG = "FILE WRITE ERROR, RENDER ABORTED !"
                    RENDER_STARTED = -1
                    break
                except:
                    REND_MSG = "EXPORT FAILED, RENDER ABORTED !"
                    RENDER_STARTED = -1
                    ShowError()
                    break
                else:
                    if numobs==0:
                        REND_MSG = "NO OBJECTS EXPORTED, RENDER ABORTED"
                        RENDER_STARTED = -1
                        break
                    elif (numlamps==0) and (TWORLD_LIGHT.val==0):
                        REND_MSG = "NO LIGHTS EXPORTED, RENDER ABORTED"
                        RENDER_STARTED = -1
                        break
                sys.stdout.flush()  # just in case, for win
                # start render
                REND_MSG = 'Rendering frame %d' % currentframe
## jms : modif 16/08/2003
                if BL_VERSION<228:   
                   Blender.Window.Redraw(Blender.Window.Const.TEXT)
                else: 
                   Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003
                """
                Blender.Window.Redraw(Blender.Window.Const.TEXT)
                """

                # wait for Lightflow to finish rendering, LFPID will now contain exitcode
                StartLightflow(1)
                # check if it exited with an error
                if LFPID==1:
                    # Python/Lightflow failed, stop immediately
                    REND_MSG = "PYTHON/LIGHTFLOW FAILURE !!! RENDER ABORTED"
                    raise Exception(REND_MSG)
                # get the targa file
                LoadRawTGA()
                # display it
## jms : modif 16/08/2003
                if BL_VERSION<228:   
                   Blender.Window.Redraw(Blender.Window.Const.TEXT)
                else: 
                   Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003
                """
                Blender.Window.Redraw(Blender.Window.Const.TEXT)
                """ 
            except KeyboardInterrupt:
                REND_MSG = 'Rendering aborted...'
                # show last image in case it was not displayed yet
                LoadRawTGA()
                # display it
## jms : modif 16/08/2003
                if BL_VERSION<228:   
                   Blender.Window.Redraw(Blender.Window.Const.TEXT)
                else: 
                   Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003
                """
                Blender.Window.Redraw(Blender.Window.Const.TEXT)
                """

                break
            except:
                ShowError()
                break
            else:
                REND_MSG = "Ready!"
        # break starts here
        # export finished/aborted
        sys.stdout.flush()  # just in case, for win
        ANIM_STARTED = 0
        # reset LFPID to -1, since here it is not an actual PID (exitcode, os.P_WAIT was used), and might confuse the script
        # when switching to settings screen and back again to render
        LFPID = -1
        # remove the (temporary) _ATMP.py
        GetOutdir()
        try:
            os.remove(pyfilepath)
        except:
            print "Could not delete temporary file: ", pyfilepath
        # Set frame back to frame when started (not necessarily 'staframe')
        if BL_VERSION<=223 or BL_VERSION>=228:
            Blender.Set('curframe', cframe)
        else:
            curscene = Blender.Scene.getCurrent()
            curscene.frameSettings(curscene.startFrame(), curscene.endFrame(), cframe)
## jms : modif 16/08/2003
        if BL_VERSION<228:   
            Blender.Window.Redraw(Blender.Window.Const.VIEW3D)
            Blender.Window.Redraw(Blender.Window.Const.TEXT)
        else: 
            Blender.Window.Redraw(Blender.Window.Types['VIEW3D'])
            Blender.Window.Redraw(Blender.Window.Types['TEXT'])
## jms : modif 16/08/2003
        """
        Blender.Window.Redraw(Blender.Window.Const.VIEW3D)
        Blender.Window.Redraw(Blender.Window.Const.TEXT)
        """

##################################################
# SUBROUTINES FOR THE PATH GUI                   #
##################################################

def pt_draw():
    global Tpath,TLFpath,TMPpath, Tsave_path, Teditpath, Tmsp_path, Ttex_dir, Tpy_execpath
    global Tbrowser

    getBGC()
    BGL.glClear(BGL.GL_COLOR_BUFFER_BIT)
    
    mid, mulx, muly = GetWindowFactors()
    Lstart = 10*mulx

    BGL.glColor3f(1,0,0)
    BGL.glRasterPos2i(Lstart, 495*muly)
    Draw.Text(PATH_TITLE)

    BGL.glColor3f(0,0,0)
    BGL.glRasterPos2i(Lstart, 480*muly)
    Draw.Text("Please type in the full path to your prefered export directory")

    # the path string input
    Tpath = Draw.String("LFExport: ", evt_ignore, Lstart, 470*muly, 375*mulx, 18*muly, Tpath.val, 128,
                        "The full path to the LFexport directory")
    TLFpath = Draw.String("LF path: ", evt_ignore, Lstart, 450*muly, 375*mulx, 18*muly, TLFpath.val, 128,
                        "The full path to the LIGHTFLOWPATH directory")
    TMPpath = Draw.String("LFtemp path: ", evt_ignore, Lstart, 430*muly, 375*mulx, 18*muly, TMPpath.val, 128,
                        "The full path to the LIGHTFLOWTEMP directory")

    # optional python path for rendering from blender
    # only needed for windows
    BGL.glRasterPos2i(Lstart, 425*muly)
    if sys.platform=='win32':
        #Draw.Text("You are using Windows.")
        BGL.glRasterPos2i(Lstart, 400*muly)
        Draw.Text('The script uses the current running python version to be able to render.')
        BGL.glRasterPos2i(Lstart, 385*muly)
        Draw.Text('The full path to the python executable was determined to be:')
        Tpy_execpath = Draw.String("pypath: ", evt_ignore, Lstart, 360*muly, 375*mulx, 18*muly, Tpy_execpath.val, 128,
                                    "Full path to the current python executable")
        BGL.glColor3f(0, 0, 0)
        BGL.glRasterPos2i(Lstart, 345*muly)
        Draw.Text('If this is not correct, please specify the correct name.')
    elif sys.platform.find('linux')!=-1:
        #Draw.Text("This OS is Linux")
        BGL.glRasterPos2i(Lstart, 400*muly)
        Draw.Text('For documentation: What browser do you prefer to use?')
        BGL.glRasterPos2i(Lstart, 385*muly)
        Draw.Text('Choose from the menu below (only 4 choices, sorry...)')
        Tbrowser    =   Draw.Menu("BROWSER%t|Default%x0|Konquerer%x1|Mozilla%x2|Netscape%x3", evt_ignore,
                        Lstart, 360*muly, 150*mulx, 18*muly, Tbrowser.val, "Choose your prefered browser")
        # Browse test button
        Draw.Button("TEST BROWSER", evt_testbrowser, Lstart+160*mulx, 360*muly, 100*mulx, 18*muly, "Test if the browser can be opened")
    else:
        Draw.Text(sys.platform + " ??? What do you need this script for ???")

    # choosing a text editor
    BGL.glColor3f(0,0,0)
    BGL.glRasterPos2i(Lstart, 255*muly)
    Draw.Text("Specify the name (plus full path if not in system path) of")
    BGL.glRasterPos2i(Lstart, 240*muly)
    Draw.Text("the editor you want to use to edit exported .py files.")
    BGL.glRasterPos2i(Lstart, 225*muly)
    Draw.Text("You can simply ignore this if you don't need it.")
    Teditpath = Draw.String("Text Editor: ", evt_ignore, Lstart, 200*muly, 265*mulx, 18*muly, Teditpath.val, 128,
                    "The full path to your prefered texteditor")
    Draw.Button("TEST EDITOR", evt_tested, Lstart+265*mulx, 200*muly, 110*mulx, 18*muly, "Test if the editor works")

    # If MSPint module could be imported, get MATSpiderLF path
    if MSPOK:
        BGL.glRasterPos2i(Lstart, 180*muly)
        Draw.Text("Specify the full path to your MATSpider directory below.")
        BGL.glRasterPos2i(Lstart, 165*muly)
        Draw.Text("Use button next to it to see if it is correct.")
        Tmsp_path = Draw.String("MATSpider dir: ", evt_ignore, Lstart, 140*muly, 265*mulx, 18*muly, Tmsp_path.val, 128,
                    "The full path to the main MATSpiderLF directory")
        Draw.Button("TEST MSPIDER", evt_testmsp, Lstart+265*mulx, 140*muly, 110*mulx, 18*muly, "Test if the MATSpider directory is correct")
        if MSP_PATHOK[0]:
            BGL.glColor3f(0, 0.5, 0)
        else:
            BGL.glColor3f(1,0,0)
        BGL.glRasterPos2i(Lstart, 120*muly)
        Draw.Text(MSP_PATHOK[1])

    # Now the directory where all textures can be found, necessary since Blender210 module really needs to go
    BGL.glColor3f(0,0,0)
    BGL.glRasterPos2i(Lstart, 100*muly)
    Draw.Text("Specify the full path to your main texture image directory.")
    Ttex_dir = Draw.String("Texture dir: ", evt_ignore, Lstart, 75*muly, 375*mulx, 18*muly, Ttex_dir.val, 128, "Full path to your main texture directory")

    if not PATH_OK[0]:
        BGL.glColor3f(1, 0, 0)
        BGL.glRasterPos2i(Lstart, 40*muly)
        Draw.Text(PATH_OK[1])

    # save button
    Tsave_path = Draw.Button("SAVE ALL", evt_save, Lstart, 10*muly, 90*mulx, 18*muly, "Only click after everything is set!")

    # Extra cancel button when called from main GUI
    if PREF_CANCEL:
        Draw.Button("CANCEL", evt_ptcancel, 300*mulx, 10*muly, 75*mulx, 18*muly)


def pt_bevent(evt):
    global PATH_OK, LFXPORT, LFE_scene_filepath, MSP_PATHOK, MSP_PATH, TEXROOT
    if evt == evt_save:
        # test and create root output directory
        LFXPORT = Tpath.val
        LFHOME  = TLFpath.val
        LFTEMP  = TMPpath.val

        # TEST THAT THE SPECIFIED PYTHON.EXE IS CORRECT
        if not os.path.exists(Tpy_execpath.val):
            # not correct
            PATH_OK = [0, "The specified Python location does not exist !!!"]
            Blender.Redraw()
            return
            
        if not os.path.exists(TLFpath.val):
            # not correct
            PATH_OK = [0, "The specified Lightflow path does not exist !!!"]
            Blender.Redraw()
            return

        if LFXPORT=='':
            # nothing there
            PATH_OK = [0, "You did not specify the Export directory !!!"]
            Blender.Redraw()
            return

        # since texture dir is initially empty, force user to specify it
        if not len(Ttex_dir.val):
            PATH_OK = [0, "You did not specify the texture directory !!!"]
            Blender.Redraw()
            return

        # Test if the texture directory is an existing directory
        if not os.path.exists(Ttex_dir.val):
            PATH_OK = [0, "The specified texture directory does not exist!!!"]
            Blender.Redraw()
            return

        # Create Export directory if it does not exist yet
        PATH_OK = [1, '']
        if not os.path.exists(LFXPORT):
            try:
                os.mkdir(LFXPORT)
            except OSError:
                PATH_OK = [0, ("Can't create directory with name '%s'" % LFXPORT)]
                Blender.Redraw()
            else:
                print "%s directory created" % LFXPORT
        else:
            print "Ready: %s" % LFXPORT

        if PATH_OK[0]:
            # SAVE THE PATH SETTINGS IN THE LIGHTFLOW DIRECTORY
            pfilename = os.path.join(sfilepath, LFE_paths_filename)
            print "Saving paths to",pfilename
            try:
                # catch filewrite errors
                fh = open(pfilename, 'wb')
                # NOW ADDED FOR ID PURPOSES, VERSION NUMBER FIRST
                fh.write(str(LFE_ID)+'\n')
                # Main Lightflow export directory
                fh.write(LFXPORT + '\n')
                # LIGHTFLOWPATH
                fh.write(LFHOME + '\n')
                # LIGHTFLOWTEMP
                fh.write(LFTEMP + '\n')
                # Editor name only
                fh.write(Teditpath.val+'\n')
                # MATSpider directory name
                fh.write(Tmsp_path.val+'\n')
                # texture directory name
                fh.write(Ttex_dir.val+'\n')
                # stupid mistake, forgot pythonpath
                fh.write(Tpy_execpath.val+'\n')
                # linux only, browser preference
                if sys.platform!='win32':
                    fh.write(str(Tbrowser.val)+'\n')
                fh.close()
            except IOError as st:
                PATH_OK = [0, "Error writing pathfile!"]
                print st
                try:    # fh might not be open
                    if not fh.closed: fh.close()
                except:
                    pass
            else:
                PATH_OK = [1, "Saved pathfile."]
                # The LFE_scene_filepath variable was missing here, which caused
                # an error when exporting for the first time after path definitions
                GetOutdir()
                LFE_scene_filepath = os.path.join(outdir, LFE_scene_filename)
                MSP_PATH = Tmsp_path.val
                TEXROOT = Ttex_dir.val
                # Now try to load the scene settings file if there is one
                READ_SETTINGS()

                # Set the display sizes accordingly.
                # Since I can switch back and forth between old and new API, check version anyway,
                # as a scene file might be read which specifies settings from Blender, so force 4:3 menu, just in case
                if BL_VERSION>223: Timsi_pref.val = 0
                main_bevent(evt_imgsize)    # fake event to set the X & Y resolution

                # Initialize MATSpider if available
                INIT_MATSPIDER()
                # now start the real LFGUI
                Draw.Register(main_draw, main_event, main_bevent)

    elif evt == evt_fsel:
        # start the file-selector
        FileSelect()
    elif evt == evt_testbrowser:
        # Try to open the webbrowser, use the GeneralInfo.html file
        fname = os.path.join(LFHOME, 'PM/LFE_DOCS/GeneralInfo.html')
        BROWSER_OPEN(fname)
    elif evt == evt_tested:
        # Try to start the editor
        try:
            os.system(Teditpath.val)
        except:
            print "Can't find or start "+Teditpath.val
    elif evt == evt_testmsp:
        # Test if MATSpider directory is valid by testing the directory itself,
        # and testing if MATSpiderLib.dll and 'Library' directory are inside it.
        if os.path.exists(Tmsp_path.val):
            # dll name
            dln = os.path.normpath(os.path.join(Tmsp_path.val, "MATSpiderLib.dll"))
            # libdir name
            lbn = os.path.normpath(os.path.join(Tmsp_path.val, "Library"))
            print dln, lbn
            if os.path.exists(dln) and os.path.exists(lbn):
                MSP_PATHOK = [1, "MATSpider directory correct"]
            else:
                MSP_PATHOK = [0, "Invalid MATSpider directory"]
        else:
            MSP_PATHOK = [0, "Directory does not exist"]
        Blender.Redraw()
    elif evt == evt_ptcancel:
        # Cancelled, restart main GUI
        Draw.Register(main_draw, main_event, main_bevent)


################################
# SCENE SETTINGS FILE DEFAULTS #
################################

def SetDefaults():
    # re-initializes all buttons to default values
    global Tsavestuff, Tautocheck, Tradiosity, Tcaustics, Tanimation
    global TWORLD_LIGHT, TWORLD_SIZE, TWORLD_COLOR_R, TWORLD_COLOR_G, TWORLD_COLOR_B, TWORLD_TEX
    global Ttrace_depth, Tradio_depth, Tradio_samples
    global Tphoton_count, Tpcluster_d, Tpcluster_c
    global Tlayer
    global Tdof_method, Tdof_radius, Tdof_mask, Tdof_autofocus, Tdof_aperture
    global Thalo_toggle, Thalo_lens_kr, Thalo_lens_km, Thalo_lens_sh
    global Tglit_toggle, Tglit_radius, Tglit_intens, Tglit_thold
    global Tfilm_toggle, Tfilm_grain
    global Tvolum_toggle, Tvolum_sampling, Tvolum_denscach
    # default engine
    global Tdisp_switch, Tshad_switch, Tvolm_switch
    global Trad_sampling, Trad_thold, Trusedist_scr, Trusedist_max, Trusedist_min
    global Tlight_accur, Tlight_count, Tlight_depth, Tlight_thold
    # anti-alias
    global Taa_samples1, Taa_samples2, Taa_thold, Taa_jitter
    # render engine preset
    global Trender_preset
    # image size
    global Timsi_pref, Timsi_percent, Timsi_CustX, Timsi_CustY
    # rad.calc for _GLAS & METL, texture memory size
    global Trad_glas, Trad_metl, TCPU
    # Caching parameters
    global Tcache_switch, Tcache_size, Tcache_cells, Tcache_minrad, Tcache_maxrad
    # Layer buttons
    global Tlayer_switch
    # Shadowmap parameters
    global Tsmap_zbuf, Tsmap_samples, Tsmap_bias
    # Refraction/Reflection blur
    global Trblur_samples
    # Autodisplay buttons
    global Tautodisp_toggle, Tautodisp_interv
    # Blendfile import
    global Tblendimp
    # docmenu
    global Tdocmenu

    Tsavestuff  = Draw.Create(0)
    Tautocheck  = Draw.Create(0)
    Tradiosity  = Draw.Create(0)
    Tcaustics   = Draw.Create(0)
    Tanimation  = Draw.Create(0)

    TWORLD_LIGHT    = Draw.Create(0)
    TWORLD_SIZE     = Draw.Create(50.0)
    TWORLD_COLOR_R  = Draw.Create(1.0)
    TWORLD_COLOR_G  = Draw.Create(1.0)
    TWORLD_COLOR_B  = Draw.Create(1.0)
    TWORLD_TEX      = Draw.Create("None")

    Ttrace_depth    = Draw.Create(4)
    Tradio_depth    = Draw.Create(4)
    Tradio_samples  = Draw.Create(400)
    Tphoton_count   = Draw.Create(300000)
    Tpcluster_d     = Draw.Create(1000)
    Tpcluster_c     = Draw.Create(50)

    Tlayer          =   Draw.Create(-1) # -1 = all layers, individual layers = bits 0-19

    Tdof_method     =   Draw.Create(0)
    Tdof_radius     =   Draw.Create(0.01)
    Tdof_mask       =   Draw.Create(20)
    Tdof_autofocus  =   Draw.Create(0)
    Tdof_aperture   =   Draw.Create(0.0)

    Thalo_toggle    =   Draw.Create(0)
    Thalo_lens_kr   =   Draw.Create(0.02)
    Thalo_lens_km   =   Draw.Create(0.01)
    Thalo_lens_sh   =   Draw.Create(0.0)

    Tglit_toggle    =   Draw.Create(0)
    Tglit_radius    =   Draw.Create(0.1)
    Tglit_intens    =   Draw.Create(0.005)
    Tglit_thold     =   Draw.Create(0.5)

    Tfilm_toggle    =   Draw.Create(0)
    Tfilm_grain     =   Draw.Create(0.1)

    Tvolum_toggle   =   Draw.Create(0)
    Tvolum_sampling =   Draw.Create(40.0)
    Tvolum_denscach =   Draw.Create(2048)

    Tdisp_switch    =   Draw.Create(1)
    Tshad_switch    =   Draw.Create(1)
    Tvolm_switch    =   Draw.Create(1)
    Trad_sampling   =   Draw.Create(0)
    Trad_thold      =   Draw.Create(0.2)
    Trusedist_scr   =   Draw.Create(0.25)
    Trusedist_max   =   Draw.Create(0.4)
    Trusedist_min   =   Draw.Create(0.01)
    Tlight_accur    =   Draw.Create(0.98)
    Tlight_count    =   Draw.Create(1)
    Tlight_depth    =   Draw.Create(5)
    Tlight_thold    =   Draw.Create(0.05)

    Taa_samples1    =   Draw.Create(2)
    Taa_samples2    =   Draw.Create(4)
    Taa_thold       =   Draw.Create(0.07)
    Taa_jitter      =   Draw.Create(0.5)

    Trender_preset  =   Draw.Create(0)

    # default = 'Blender settings' if Blender version <= 223, otherwise default to 640 X 480
    if BL_VERSION<=223:
        Timsi_pref  =   Draw.Create(3)
    else:
        Timsi_pref  =   Draw.Create(0)
    # default to 100 percent for non-blender image size
    Timsi_percent   =   Draw.Create(100)
    # Actual image size
    if BL_VERSION<=223:
        ds = Blender210.getDisplaySettings()
        Timsi_CustX =   Draw.Create(ds.xResolution)
        Timsi_CustY =   Draw.Create(ds.yResolution)
    else:
        Timsi_CustX =   Draw.Create(640)
        Timsi_CustY =   Draw.Create(480)

    # switches, radiosity calculations for _GLAS & METL
    Trad_glas           =   Draw.Create(0)
    Trad_metl           =   Draw.Create(1)  # metal is enabled by default
    TCPU                =   Draw.Create(1)  # Number of processors used
    # Caching parameters, defaults from MATSpiderLF fast_preview.mtl
    Tcache_switch       =   Draw.Create(0)
    Tcache_size         =   Draw.Create(1000)
    Tcache_cells        =   Draw.Create(100)
    Tcache_minrad       =   Draw.Create(0.1)
    Tcache_maxrad       =   Draw.Create(0.3)

    # The layer button array, 20 toggle switches
    Tlayer_switch = []
    for i in range(20):
        Tlayer_switch.append(Draw.Create(1))    # All on by default

    # DOCUMENTATION MENU
    Tdocmenu = Draw.Create(0)

    # Shadowmap parameters
    Tsmap_zbuf      =   Draw.Create(256)
    Tsmap_samples   =   Draw.Create(6)
    Tsmap_bias      =   Draw.Create(0.2)

    # Reflection/Refraction blur
    Trblur_samples  =   Draw.Create(3)

    # Autodisplay buttons
    Tautodisp_toggle    =   Draw.Create(0)
    Tautodisp_interv    =   Draw.Create(3.0)

    # Blendfile import
    Tblendimp           =   Draw.Create(0)


###############################################
# SETTINGS FILE WITH ALL PARAMETERS AND PATHS #
###############################################

def WRITE_SETTINGS():
    # packed data string
    st = TWORLD_TEX.val+'\n'
    st += pack('l', Tsavestuff.val)
    st += pack('l', Tautocheck.val)
    st += pack('l', Tradiosity.val)
    st += pack('l', Tcaustics.val)
    st += pack('l', Tanimation.val)
    st += pack('l', TWORLD_LIGHT.val)
    st += pack('f', TWORLD_SIZE.val)
    st += pack('f', TWORLD_COLOR_R.val)
    st += pack('f', TWORLD_COLOR_G.val)
    st += pack('f', TWORLD_COLOR_B.val)
    st += pack('l', Ttrace_depth.val)
    st += pack('l', Tradio_depth.val)
    st += pack('l', Tradio_samples.val)
    st += pack('l', Tphoton_count.val)
    st += pack('l', Tpcluster_d.val)
    st += pack('l', Tpcluster_c.val)
    st += pack('l', Tlayer.val)
    # imagers
    st += pack('l', Tdof_method.val)
    st += pack('f', Tdof_radius.val)
    st += pack('l', Tdof_mask.val)
    st += pack('l', Tdof_autofocus.val)
    st += pack('f', Tdof_aperture.val)
    st += pack('l', Thalo_toggle.val)
    st += pack('f', Thalo_lens_kr.val)
    st += pack('f', Thalo_lens_km.val)
    st += pack('f', Thalo_lens_sh.val)
    st += pack('l', Tglit_toggle.val)
    st += pack('f', Tglit_radius.val)
    st += pack('f', Tglit_intens.val)
    st += pack('f', Tglit_thold.val)
    st += pack('l', Tfilm_toggle.val)
    st += pack('f', Tfilm_grain.val)
    # volumetric options
    st += pack('l', Tvolum_toggle.val)
    st += pack('f', Tvolum_sampling.val)
    # default engine
    st += pack('l', Tdisp_switch.val)
    st += pack('l', Tshad_switch.val)
    st += pack('l', Tvolm_switch.val)
    st += pack('l', Trad_sampling.val)
    st += pack('f', Trad_thold.val)
    st += pack('f', Trusedist_scr.val)
    st += pack('f', Trusedist_max.val)
    st += pack('f', Trusedist_min.val)
    st += pack('f', Tlight_accur.val)
    st += pack('l', Tlight_count.val)
    st += pack('l', Tlight_depth.val)
    st += pack('f', Tlight_thold.val)
    # anti-alias
    st += pack('l', Taa_samples1.val)
    st += pack('l', Taa_samples2.val)
    st += pack('f', Taa_thold.val)
    st += pack('f', Taa_jitter.val)
    st += pack('l', Trender_preset.val)
    # image size, only preferences and percentage, XY calculated from it, no need to save
    st += pack('l', Timsi_pref.val)
    st += pack('l', Timsi_percent.val)
    # switches, radiosity calculations for _GLAS & METL
    st += pack('l', Trad_glas.val)
    st += pack('l', Trad_metl.val)
    # number of processors
    st += pack('l', TCPU.val)
    # Caching parameters
    st += pack('l', Tcache_switch.val)
    st += pack('l', Tcache_size.val)
    st += pack('l', Tcache_cells.val)
    st += pack('f', Tcache_minrad.val)
    st += pack('f', Tcache_maxrad.val)
    # Shadowmap parameters
    st += pack('l', Tsmap_zbuf.val)
    st += pack('l', Tsmap_samples.val)
    st += pack('f', Tsmap_bias.val)
    # Refraction/Reflection blur
    st += pack('l', Trblur_samples.val)
    # volumetric option
    st += pack('l', Tvolum_denscach.val)
    # Last added blendfile import option, placed here, otherwise old settings files will be interpreted wrongly
    st += pack('l', Tblendimp.val)

    GetOutdir()
    LFE_scene_filepath = os.path.join(outdir, LFE_scene_filename)
    OK = 0
    try:
        settings = open(LFE_scene_filepath, 'wb')
        settings.write(st)
        settings.close()
        OK = 1
    except:
        try:    # settings file might still be open
            print "error, closing settings"
            if not settings.closed: settings.close()
        except:
            pass
    return OK


def READ_SETTINGS():
    global Tsavestuff, Tautocheck, Tradiosity, Tcaustics, Tanimation
    global TWORLD_LIGHT, TWORLD_SIZE, TWORLD_COLOR_R, TWORLD_COLOR_G, TWORLD_COLOR_B, TWORLD_TEX
    global Ttrace_depth, Tradio_depth, Tradio_samples
    global Tphoton_count, Tpcluster_d, Tpcluster_c
    global Tlayer
    global Tdof_method, Tdof_radius, Tdof_mask, Tdof_autofocus, Tdof_aperture
    global Thalo_toggle, Thalo_lens_kr, Thalo_lens_km, Thalo_lens_sh
    global Tglit_toggle, Tglit_radius, Tglit_intens, Tglit_thold
    global Tfilm_toggle, Tfilm_grain
    global Tvolum_toggle, Tvolum_sampling, Tvolum_denscach
    # default engine
    global Tdisp_switch, Tshad_switch, Tvolm_switch
    global Trad_sampling, Trad_thold, Trusedist_scr, Trusedist_max, Trusedist_min
    global Tlight_accur, Tlight_count, Tlight_depth, Tlight_thold
    # anti-alias
    global Taa_samples1, Taa_samples2, Taa_thold, Taa_jitter
    # render engine preset
    global Trender_preset
    # image size
    global Timsi_pref, Timsi_percent
    # rad.calc for _GLAS & METL, number of processors
    global Trad_glas, Trad_metl, TCPU
    # Caching parameters
    global Tcache_switch, Tcache_size, Tcache_cells, Tcache_minrad, Tcache_maxrad
    # All layer switches
    global Tlayer_switch
    # Shadowmap parameters
    global Tsmap_zbuf, Tsmap_samples, Tsmap_bias
    # Refraction/reflection blur
    global Trblur_samples
    # Blendfile import
    global Tblendimp

    # First set everything to defaults, so that in the event that an old scene file is read,
    # or the compiled file is started after deleting directory contents (global inits in that case not done),
    # at least all variables will be (re-)initialized
    SetDefaults()

    # Get name from Blender
    GetOutdir()
    LFE_scene_filepath = os.path.join(outdir, LFE_scene_filename)
    try:
        sfile = open(LFE_scene_filepath, 'rb')
    except IOError:
        print "No scene info, assuming new scene!"
    else:
        try:
            # try reading settings for this scene
            settings = sfile.read()
            sfile.close()
        except:
            print "Scene settings file corrupt, using defaults instead!"
            try:    # close settings file if open
                if not sfile.closed: sfile.close()
            except:
                pass
            # may have partly been read, so have to redefine to default
            SetDefaults()
        else:

            # unpack data and initialize buttons
            # split texture name and remainder of data
            ds = settings.split('\n', 1)
            TWORLD_TEX = Draw.Create(ds[0])
            ds = ds[1]
            # catch unpack errors from old settings files
            try:
                Tsavestuff      =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tautocheck      =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]     
                Tradiosity      =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tcaustics       =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tanimation      =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                TWORLD_LIGHT    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                TWORLD_SIZE     =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                TWORLD_COLOR_R  =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                TWORLD_COLOR_G  =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                TWORLD_COLOR_B  =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Ttrace_depth    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tradio_depth    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tradio_samples  =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tphoton_count   =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tpcluster_d     =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tpcluster_c     =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tlayer          =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                # imagers
                Tdof_method     =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tdof_radius     =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Tdof_mask       =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tdof_autofocus  =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tdof_aperture   =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Thalo_toggle    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Thalo_lens_kr   =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Thalo_lens_km   =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Thalo_lens_sh   =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Tglit_toggle    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tglit_radius    =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Tglit_intens    =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Tglit_thold     =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Tfilm_toggle    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tfilm_grain     =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                # volumetric options
                Tvolum_toggle   =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tvolum_sampling =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                # default engine
                Tdisp_switch    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tshad_switch    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tvolm_switch    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Trad_sampling   =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Trad_thold      =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Trusedist_scr   =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Trusedist_max   =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Trusedist_min   =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Tlight_accur    =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Tlight_count    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tlight_depth    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tlight_thold    =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                # CAMERA ANTI-ALIAS OPTIONS
                Taa_samples1    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Taa_samples2    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Taa_thold       =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Taa_jitter      =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Trender_preset  =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                # IMAGE SIZE
                Timsi_pref      =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Timsi_percent   =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                # switches, radiosity calculations for _GLAS & METL
                Trad_glas       =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Trad_metl       =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                TCPU            =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                # since this might be read from a old file where this was texture memory,
                # make sure the number is not over 16
                if TCPU.val>16: TCPU.val = 16
                # Caching parameters
                Tcache_switch   =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tcache_size     =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tcache_cells    =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tcache_minrad   =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                Tcache_maxrad   =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                # Shadowmap parameters
                Tsmap_zbuf      =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tsmap_samples   =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                Tsmap_bias      =   Draw.Create(unpack('f', ds[:4])[0]);        ds = ds[4:]
                # Refraction/reflection blur
                Trblur_samples  =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                # volumetric option
                Tvolum_denscach =   Draw.Create(unpack('l', ds[:4])[0]);        ds = ds[4:]
                # Last added blendfile option, placed here, otherwise old settings files will be interpreted wrongly
                # (wrong parameters will be assigned)
                Tblendimp       =   Draw.Create(unpack('l', ds[:4])[0])

            except:
                print "Possibly old settings file, some variables set to default values!"

            # Set all layer switches according to the bitmask from Tlayer
            Tlayer_switch = []
            for i in range(20):
                bit = (1 << i)
                Tlayer_switch.append(Draw.Create(((bit & Tlayer.val)==bit)))


def GetOutdir():
    # EXTRACT A NAME FROM THIS BLENDFILE.
    # THIS WILL BE USED FOR THE DIRECTORY NAMES, .PY, & .TGA FILES
    # ALSO USED FOR .RAD (RADIOSITY RESULTS) AND .LAMP (SHADOWMAP) FILES
    global outdir, outname, frame_outname, pyname, pyfilepath, imgdir, tgatex_dir, alldata_dir

    outname = Blender.Get('filename')       # NAME OF BLENDFILE
    HT = os.path.split(outname)             # (DIR, FILE)
    outname = os.path.splitext(HT[1])[0]    # FILE MINUS EXTENSION (.blend)

    # reported by 'fullback': some people will have the habit of using spaces in filenames
    # so replace the spaces with underscores in the output filename
    outname = outname.replace(' ', '_')
    outdir = os.path.join(LFXPORT, outname)

    # construct.py filename and path
    # get frame number and append to 
    cframe = Blender.Get('curframe')
    frame_outname = outname + "_" + ("%04d" % cframe)   # for .PY and .TGA
    # IF THIS IS AN ANIMATION, DON'T ADD FRAME NUMBER TO IT
    # WE ONLY WANT TO WRITE ONE PYTHON FILE
    if Tanimation.val==1:
        pyname = outname + "_ATMP.py"   # render-from-blender animation pyfile is temporary
    elif Tanimation.val==2:
        pyname = "ANIM_" + outname + ".py"  # single file full animation export
    else:
        pyname = frame_outname + ".py"
    pyfilepath = os.path.join(outdir, pyname)
    # Create pathname for image directory
    imgdir = os.path.join(outdir, 'ImgSequence')
    # Create pathname for converted textures
    tgatex_dir = os.path.join(outdir, 'TGA_Textures')
    # Create pathname for all data (.mesh and animation.dat)
    alldata_dir = os.path.join(outdir, 'DATA')


def WriteDirsSettings():
    # creating file output directories and write settings file
    if not os.path.exists(outdir):
        try:
            os.mkdir(outdir)
        except OSError:
            raise Exception("Could not create file output directory")
        else:
            print "%s directory created" % outdir
    else:
        print "%s already exists" % outdir

    # Create the image dir for animation sequence
    if not os.path.exists(imgdir):
        try:
            os.mkdir(imgdir)
        except OSError:
            raise Exception("Could not create image output directory")
        else:
            print "%s directory created" % imgdir
    else:
        print "%s already exists" % imgdir

    # Create the tga texture dir for converted textures
    if not os.path.exists(tgatex_dir):
        try:
            os.mkdir(tgatex_dir)
        except OSError:
            raise Exception("Could not create texture output directory")
        else:
            print "%s directory created" % tgatex_dir
    else:
        print "%s already exists" % tgatex_dir

    # Create the data dir for .mesh and animation.dat
    if not os.path.exists(alldata_dir):
        try:
            os.mkdir(alldata_dir)
        except OSError:
            raise Exception("Could not create data output directory")
        else:
            print "%s directory created" % alldata_dir
    else:
        print "%s already exists" % alldata_dir

    # WRITE ALL SETTINGS TO SETTINGS FILE
    if not WRITE_SETTINGS(): raise Exception("Settingsfile write error")


# A function to find a full path to a file matching the argument (possibly incomplete fragment), in any directory starting with 'root'
# Adapted from a function found in the ASPN's Python cookbook, a great source of useful tips & tricks
# The pattern matching was removed (can't import fnmatch in Blender on Linux?)
def WalkFind(root, recurse=0, pattern=''):
    # initialize
    result = []
    # must have at least root folder
    try:
        names = os.listdir(root)
    except os.error:
        return result
    # check each file
    for name in names:
        fullname = os.path.normpath(os.path.join(root, name))
        # grab if it matches our pattern and entry type
        # In case the name is exactly the same, nothing to be done further
        # only the name needs to be compared with pattern, fullname is used for result
        if name==pattern:
            if os.path.isfile(fullname):
                result = [fullname]
                break
        elif name.find(pattern)!=-1:
            if os.path.isfile(fullname):
                result.append(fullname)
        # recursively scan other folders, appending results
        if recurse:
            if os.path.isdir(fullname) and not os.path.islink(fullname):
                result += WalkFind(fullname, recurse, pattern)
    return result


def START_PATH_GUI():
    global sfilepath,Tpath,TLFpath,TMPpath, Teditpath, Tmsp_path, PREF_CANCEL, Tpy_execpath
    # Create a preset editor name based on platform, windows users probably will use notepad anyway
    # For windows also create preset pathname for MATSpiderLF
    # For both create LFexport preset name

    # construct the path to the python executable using the main python directory name in PYTHONPATH
    if sys.platform=='win32':
        # different method, like install script using python lib directory
        # ;=os.pathsep 
        # pt = os.environ['PYTHONPATH'].split(os.pathsep)
        print 'PYPATH',PYPATH
        pt = PYPATH.split(os.pathsep)
        py_exedir = None
        for p in pt:
            ok = p.lower().find('lib')
            if ok!=-1:
                py_exedir = p[:ok]
                break
        if py_exedir:
            Tpy_execpath = Draw.Create(os.path.join(py_exedir, 'python.exe'))
        else:
            # not found(???), use old method, user has to specify it...
            #Tpy_execpath = Draw.Create(os.path.join(os.path.commonprefix(os.environ['PYTHONPATH'].split(os.pathsep)), 'python.exe'))
            Tpy_execpath = Draw.Create(os.path.join(os.path.commonprefix(pt), 'python.exe'))
    else:
        # method above can't be used in Linux, assume /usr/bin/python or /usr/local/bin/python
        tpy = "/usr/bin/python"
        if os.path.exists(tpy):
            Tpy_execpath = Draw.Create(tpy)
        else:
            tpy = "/usr/local/bin/python"
            if os.path.exists(tpy):
                Tpy_execpath = Draw.Create(tpy)
            else:
                raise Exception("Sorry, can't find python binary path...")

    if sys.platform=='win32':
        # try using drive name where windows is located
        dr = os.path.splitdrive(os.environ['WINDIR'])
        #TLFpath  = Draw.Create(dr[0] + "\Lightflow")
        TLFpath  = Draw.Create(LFHOME)
        #TMPpath  = Draw.Create(dr[0] + "\Lightflow\LFtemp")
        TMPpath  = Draw.Create(LFTEMP)
        Tpath    = Draw.Create(LFXPORT)
        Teditpath = Draw.Create('Notepad')
        # MATSpider directory
        Tmsp_path = Draw.Create(dr[0] + "\PROGRA~1\MATSpiderLF")
    else:
        #dr = os.path.join(os.environ['HOME']
        dr = os.environ['HOME']
        TLFpath  = Draw.Create(dr+ 'Lightflow')
        TMPpath = Draw.Create(dr+ 'Lightflow/LFtemp')
        Tpath   = Draw.Create(dr+ 'LFexport')
        Teditpath = Draw.Create('emacs')
    PREF_CANCEL = 0
    Draw.Register(pt_draw, main_event, pt_bevent)


def INIT_MATSPIDER():
    global MSPOK, MSP_PATHOK
    # Initialize the MATSpider module
    # NOTE: don't constuct pathnames inside function argument
    # python passes strange results to module otherwise
    # catch exception in case init failed
    if MSPOK and len(MSP_PATH)>1:
        pt = MSP_PATH + '\\'
        try:
            MSPint.InitializeMSP(pt)
            MSP_PATHOK = [1, 'MATSpider path correct']
        except:
            ShowError()
            print "MATSpider path probably incorrect"
            print "The path used is: ", pt
            print "Is this correct? If not delete .LFE_paths file and start again"
            # failed, no MATSpider functions available
            MSPOK = 0


# IMPORTANT ROUTINE TO MAKE SURE SIGHANDLER IS PROPERLY RESET TO DEFAULT BEFORE EXITING
def SCRIPT_EXIT():
    # reset sig handler
    signal.signal(signal.SIGINT, signal.default_int_handler)
    # exit script
    Draw.Exit()
    print "Exited Lightflow Render GUI."


################################################
# PRIMARY CHECK AND INIT OF ALL IMPORTANT VARS #
################################################

# should have made everything a class from the start...
def START():
    global PATH_TITLE, PATH_OK, sfilepath,Tpath,TLFpath,TMPpath, LFHOME,LFTEMP,LFXPORT,PYPATH, Teditpath, Tmsp_path, MSP_PATH, Ttex_dir, TEXROOT, Timsi_pref, Tpy_execpath
    global Tbrowser

    try:
        sfilepath = Blender.Get('datadir')
        print "sfilepath",sfilepath
    except:
        print "\nNo settings path. Will try to configure."
    # test if the LIGHTFLOWPATH environment variable is available, if not, that's it, nothing more to do, goodbye...
    try:
        LFHOME = os.environ['LIGHTFLOWPATH']
    except:
        #raise Exception("\nNo LIGHTFLOWPATH, it seems you did not install Lightflow properly, goodbye...")
        print "\nNo Lightflow path. Will try to configure."
    # now do the same for PYTHONPATH, also must be available
    # but on the other hand, os probably isn't imported anyway when it is not available, but still...
    try:
        PYPATH = os.environ['PYTHONPATH']
        
    except:
        # of course can create the long string with C style separation, but looks ugly without the sudden lack
        # of the otherwise required indentation in the python code here
        #st = "\nNo PYTHONPATH, you did not set this environment variable.\nThis scipt really needs it...\n"
        #st += "So try again after you properly set this.\nFor a how-to see the GeneralInfo.html page."
        #raise Exception(st)
        print "No PYTHONPATH. Trying Blender's."
        PYPATH = os.path.abspath(os.path.join(Blender.Get('homedir'),os.pardir))


    # create full path name to settings file
    sfile = os.path.join(sfilepath, LFE_paths_filename)

    # Set all GUI vars to default
    SetDefaults()

    # now try to load the file which contains the LFexport path
    try:
        pathsfile = open(sfile)
    except IOError:
        # It did not work, start a simple GUI to allow user to input a path
        PATH_TITLE = "No path settings file !!!"
        PATH_OK = [0, PATH_TITLE]
        START_PATH_GUI()
    else:
        # try to read the path settings
        try:
            pathdata = pathsfile.read()
            pathsfile.close()
            paths = pathdata.splitlines()
            # for easier identification of old files, the first setting is now an ID
            if paths[0]!=LFE_ID:
                print "LFE_ID doesn't match"
                raise ValueError
            # Main export path
            Tpath   = Draw.Create(paths[1])
            TLFpath = Draw.Create(paths[2])
            TMPpath = Draw.Create(paths[3])
            LFXPORT = paths[1]
            LFHOME  = paths[2]
            LFTEMP  = paths[3]
            # Editor name
            Teditpath = Draw.Create(paths[4])
            # MATSpider path name (windows)
            Tmsp_path = Draw.Create(paths[5])
            MSP_PATH = paths[5]
            # Texture directory
            Ttex_dir = Draw.Create(paths[6])
            TEXROOT = paths[6]
            # Python path, totally forgotten about this in first release, really stupid...
            Tpy_execpath = Draw.Create(paths[7])
            PYPATH = paths[7]
            # linux only, browser pref.
            if sys.platform!='win32': Tbrowser = Draw.Create(int(paths[8]))
        except:
            # Path file is an old one (incomplete), start path GUI to redefine
            PATH_TITLE = "Old or corrupt path file, need new information !"
            PATH_OK = [0, PATH_TITLE]
            START_PATH_GUI()
        else:
            # Now try to load the scene settings file
            READ_SETTINGS()
            # Set the display sizes accordingly.
            # Since I can switch back and forth between old and new API, check version anyway,
            # as a scene file might be read which specifies settings from Blender, so force 4:3 menu, just in case
            if BL_VERSION>223: Timsi_pref.val = 0
            main_bevent(evt_imgsize)    # fake event to set the X & Y resolution

            # Initialize MATSpider if available
            INIT_MATSPIDER()

            # SET SIGNAL HANDLER TO STOP PYTHON FROM RESETING THE SCRIPT WHEN CTRL-C IS USED,
            # MUST BE RESET TO NORMAL WHEN EXITING, OTHERWISE NOTHING CAN BE STOPPED !!!!
            # (ALTHOUGH NOT IN 2.25, SINCE SCRIPTS ARE ONLY ACTIVE AS LONG AS THEY ARE ..... ACTIVE)
            signal.signal(signal.SIGINT, CTRLC_handler)

            # now start the LFGUI
            Draw.Register(main_draw, main_event, main_bevent)

            sys.stdout.flush()


START()

#debug 109
#Adding Lights:
#Lamp
#No PLIGHT arealights found
#Adding Scene info...