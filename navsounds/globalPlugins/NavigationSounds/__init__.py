# -*- coding: UTF-8 -*-
import globalPluginHandler
from winsound import PlaySound
import controlTypes, ui, os, speech, NVDAObjects
import config
from scriptHandler import script, getLastScriptRepeatCount
from gui import SettingsPanel, NVDASettingsDialog, guiHelper
import addonHandler
addonHandler.initTranslation()
import wx


roleSECTION = "NavigationSounds"
confspec = {
"sayRoles": "boolean(default=false)",
"soundType": "string(default=sound1)",
"rolesSounds": "boolean(default=true)"}
config.conf.spec[roleSECTION] = confspec
rolesSounds= config.conf[roleSECTION]["rolesSounds"]
sayRoles= config.conf[roleSECTION]["sayRoles"]
def loc():
	return os.path.join(os.path.abspath(os.path.dirname(__file__)), "effects",config.conf[roleSECTION]["soundType"])
#Add all the roles, looking for name.wav.
def sounds():
	sounds1 = {}
	for role in [x for x in dir(controlTypes) if x.startswith('ROLE_')]:
		r = os.path.join(loc(), role[5:].lower()+".wav")
		sounds1[getattr(controlTypes, role)] = r
	return sounds1

def getSpeechTextForProperties2(reason=NVDAObjects.controlTypes.OutputReason, *args, **kwargs):
	role = kwargs.get('role', None)
	if 'role' in kwargs and role in sounds() and os.path.exists(sounds()[role]) and sayRoles ==False:
		del kwargs['role']
	return old(reason, *args, **kwargs)

def play(role):
	"""plays sound for role."""
	f = sounds()[role]
	if os.path.exists(f) and rolesSounds==True:
		PlaySound(f, 1)

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory= _("navigation sounds")
	def __init__(self, *args, **kwargs):
		globalPluginHandler.GlobalPlugin.__init__(self, *args, **kwargs)
		NVDASettingsDialog.categoryClasses.append(NavSettingsPanel)
		global old
		old = speech.speech.getPropertiesSpeech

	def event_gainFocus(self, obj, nextHandler):
		if rolesSounds == True:
			speech.speech.getPropertiesSpeech = getSpeechTextForProperties2
			play(obj.role)
		nextHandler()

	@script(gesture="kb:NVDA+alt+n")
	def script_toggle(self, gesture):
		global rolesSounds, sayRoles
		isSameScript = getLastScriptRepeatCount()
		if isSameScript == 0:
			rolesSounds = not rolesSounds
			if rolesSounds==False:
				ui.message(_("Disable navigation sounds"))
			else:
				ui.message(_("Enable navigation sounds"))
		elif isSameScript ==1:
			sayRoles = not sayRoles
			if sayRoles ==False:
				ui.message(_("Disable sayRoles"))
			else:
				ui.message(_("Enable sayRoles"))
		config.conf[roleSECTION]["sayRoles"] = sayRoles
		config.conf[roleSECTION]["rolesSounds"] = rolesSounds
	script_toggle.__doc__= _("Pressing it once toggles between on and off object sounds, and Pressing twice  it toggles between reading and disabling object types.")
	def terminate(self):
		NVDASettingsDialog.categoryClasses.remove(NavSettingsPanel)

class NavSettingsPanel(SettingsPanel):
	title = _("navigation sounds")
	def makeSettings(self, settingsSizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.tlable = sHelper.addItem(wx.StaticText(self, label=_("select sound"), name="ts"))
		self.sou= sHelper.addItem(wx.Choice(self, name="ts"))
		self.sou.Set(os.listdir(os.path.join(os.path.abspath(os.path.dirname(__file__)), "effects")))
		self.sou.SetStringSelection(config.conf[roleSECTION]["soundType"])
		self.nas=sHelper.addItem(wx.CheckBox(self,label=_("say roles")))
		self.nas.SetValue(config.conf[roleSECTION]["sayRoles"])
		self.nab=sHelper.addItem(wx.CheckBox(self,label=_("navigation sounds")))
		self.nab.SetValue(config.conf[roleSECTION]["rolesSounds"])
	def postInit(self):
		self.sou.SetFocus()
	def onSave(self):
		global sayRoles,rolesSounds
		config.conf[roleSECTION]["soundType"]=self.sou.GetStringSelection()
		config.conf[roleSECTION]["sayRoles"]=self.nas.GetValue()
		sayRoles=config.conf[roleSECTION]["sayRoles"]
		config.conf[roleSECTION]["rolesSounds"]=self.nab.GetValue()
		rolesSounds=config.conf[roleSECTION]["rolesSounds"]