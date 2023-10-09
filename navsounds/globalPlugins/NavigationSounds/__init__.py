# -*- coding: UTF-8 -*-
import webbrowser as web
from random import choice
import globalPluginHandler
import nvwave
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
"soundType": "string(default=default)",
"rolesSounds": "boolean(default=true)",
"typing": "boolean(default=true)",
"type": "string(default=1blueSwitch)",
"edit": "boolean(default=false)",
"volume": "integer(default=100)"}
config.conf.spec[roleSECTION] = confspec
rolesSounds= config.conf[roleSECTION]["rolesSounds"]
sayRoles= config.conf[roleSECTION]["sayRoles"]

def loc():
	return os.path.join(os.path.abspath(os.path.dirname(__file__)), "effects","navsounds",config.conf[roleSECTION]["soundType"])
def loc1():
	return os.path.join(os.path.abspath(os.path.dirname(__file__)),"effects","typingsound",config.conf[roleSECTION]["type"])

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
	global playing
	f = sounds()[role]
	if os.path.exists(f) and rolesSounds==True:
		nvwave.playWaveFile(f, 1)

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory= _("navigation sounds")
	def __init__(self, *args, **kwargs):
		globalPluginHandler.GlobalPlugin.__init__(self, *args, **kwargs)
		NVDASettingsDialog.categoryClasses.append(NavSettingsPanel)
		self.playing = False
		global old
		old = speech.speech.getPropertiesSpeech
	def play1(self,l):
		if os.path.exists(os.path.join(loc1(),os.listdir(loc1())[0])) and config.conf[roleSECTION]["typing"]:
			if self.playing == True:
				nvwave.playWaveFile(os.path.join(loc1(),choice(os.listdir(loc1()))), 1)
				self.playing = False
			else:
				PlaySound(os.path.join(loc1(),choice(os.listdir(loc1()))), 1)
				self.playing = True
	def editable(self, object):
		controls = (8, 52, 82)
		return (object.role in controls or controlTypes .STATE_EDITABLE in object.states) and not controlTypes .STATE_READONLY in object.states

	def event_typedCharacter(self, obj, nextHandler, ch):
		if config.conf[roleSECTION]["edit"]:
			if self.editable(obj):
				self.play1(ch)
		else:
			self.play1(ch)
		nextHandler()
	def event_gainFocus(self, obj, nextHandler):
		if rolesSounds == True:
			speech.speech.getPropertiesSpeech = getSpeechTextForProperties2
			play(obj.role)
		nextHandler()

	@script(gesture="kb:NVDA+alt+n")
	def script_toggle(self, gesture):
		global rolesSounds
		sayRoles =config.conf[roleSECTION]["typing"]
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
				ui.message(_("Disable typing sounds"))
			else:
				ui.message(_("Enable typing sounds"))
		config.conf[roleSECTION]["typing"] = sayRoles
		config.conf[roleSECTION]["rolesSounds"] = rolesSounds
	script_toggle.__doc__= _("Pressing it once toggles between on and off object sounds, and Pressing twice  it toggles between on and off typing sounds.")
	def terminate(self):
		NVDASettingsDialog.categoryClasses.remove(NavSettingsPanel)

class NavSettingsPanel(SettingsPanel):
	title = _("navigation sounds")
	def makeSettings(self, settingsSizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.tlable = sHelper.addItem(wx.StaticText(self, label=_("select sound"), name="ts"))
		self.sou= sHelper.addItem(wx.Choice(self, name="ts"))
		self.sou.Set(os.listdir(os.path.join(os.path.abspath(os.path.dirname(__file__)), "effects","navsounds")))
		self.sou.SetStringSelection(config.conf[roleSECTION]["soundType"])
		self.nas=sHelper.addItem(wx.CheckBox(self,label=_("say roles")))
		self.nas.SetValue(config.conf[roleSECTION]["sayRoles"])
		self.nab=sHelper.addItem(wx.CheckBox(self,label=_("navigation sounds")))
		self.nab.SetValue(config.conf[roleSECTION]["rolesSounds"])
		self.ts=sHelper.addItem(wx.CheckBox(self,label=_("keyboard typing sound")))
		self.ts.SetValue(config.conf[roleSECTION]["typing"])
		self.edit=sHelper.addItem(wx.CheckBox(self,label=_("enable typing sound in text boxes only")))
		self.edit.SetValue(config.conf[roleSECTION]["edit"])
		self.tlable1 = sHelper.addItem(wx.StaticText(self, label=_("select typing sound"), name="tt"))
		self.sou1= sHelper.addItem(wx.Choice(self, name="tt"))
		self.sou1.Set(os.listdir(os.path.join(os.path.abspath(os.path.dirname(__file__)), "effects","typingsound")))
		self.sou1.SetStringSelection(config.conf[roleSECTION]["type"])
		self.tlable2 = sHelper.addItem(wx.StaticText(self, label=_("volume"), name="tt2"))
		self.sou2= sHelper.addItem(wx.SpinCtrl(self, name="tt2",min=0,max=100))
		self.sou2.SetValue(config.conf[roleSECTION]["volume"])
		self.sou2.Hide()
		b=sHelper.addItem(wx.Button(self,label=_("open sounds folder")))
		b.Bind(wx.EVT_BUTTON,self.onopen)
		donate=sHelper.addItem(wx.Button(self,label=_("donate")))
		donate.Bind(wx.EVT_BUTTON,self.ondonate)
	def postInit(self):
		self.sou.SetFocus()
	def onopen(self,event):
		os.startfile(os.path.join(os.path.abspath(os.path.dirname(__file__)), "effects"))
	def onSave(self):
		global sayRoles,rolesSounds
		config.conf[roleSECTION]["soundType"]=self.sou.GetStringSelection()
		config.conf[roleSECTION]["sayRoles"]=self.nas.GetValue()
		sayRoles=config.conf[roleSECTION]["sayRoles"]
		config.conf[roleSECTION]["rolesSounds"]=self.nab.GetValue()
		rolesSounds=config.conf[roleSECTION]["rolesSounds"]
		config.conf[roleSECTION]["typing"]=self.ts.GetValue()
		config.conf[roleSECTION]["edit"]=self.edit.GetValue()
		config.conf[roleSECTION]["type"]=self.sou1.GetStringSelection()
		config.conf[roleSECTION]["volume"]=self.sou2.GetValue()
	def ondonate(self,e):
		ui.message("please wait")
		web.open("https://www.paypal.me/ahmedthebest31")