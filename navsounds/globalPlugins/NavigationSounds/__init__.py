# -*- coding: UTF-8 -*-
import webbrowser as web
from random import choice
import globalPluginHandler
import nvwave
import controlTypes, ui, os, speech, NVDAObjects
import config
from scriptHandler import script, getLastScriptRepeatCount
from gui import SettingsPanel, NVDASettingsDialog, guiHelper
import addonHandler
addonHandler.initTranslation()
import wx


sounds1={}
roleSECTION = "NavigationSounds"
confspec = {
"sayRoles": "boolean(default=false)",
"sayStates": "boolean(default=true)",
"soundType": "string(default=default)",
"cfgSounds": "boolean(default=true)",
"typing": "boolean(default=true)",
"type": "string(default=1blueSwitch)",
"edit": "boolean(default=false)",
"volume": "integer(default=100)"}

config.conf.spec[roleSECTION] = confspec
cfgSounds= config.conf[roleSECTION]["cfgSounds"]
sayRoles= config.conf[roleSECTION]["sayRoles"]
sayStates= config.conf[roleSECTION]["sayStates"]

mainPaths=os.path.join(os.path.abspath(os.path.dirname(__file__)))
def loc():
	return os.path.join(mainPaths, "effects","navsounds",config.conf[roleSECTION]["soundType"])
def loc1():
	return os.path.join(mainPaths,"effects","typingsound",config.conf[roleSECTION]["type"])

#Add all the roles,states looking for name.wav.
def sounds(O):
	global sounds1
	if(not O.name in sounds1):
		pp = os.path.join(loc(), O.name.replace('_','').lower()+".wav")
		sounds1[O.name]=pp
	return sounds1.get(O.name)

Objects=[] #list for Objects for testing obj containts
def getSpeechTextForProperties2(reason=NVDAObjects.controlTypes.OutputReason, *args, **kwargs):
	role = kwargs.get('role', None)
	states = kwargs.get('states', None)	
	global Objects;Objects.append([kwargs,args])
	if 'role' in kwargs and os.path.exists(sounds(role)) and sayRoles ==False:
		del kwargs['role']
	if 'states' in kwargs and sayStates ==False:
		STATES=[state for state in states if os.path.exists(sounds(state))]
		for STATE in STATES:
			kwargs['states'].remove(STATE)
	return old(reason, *args, **kwargs)

	"""plays sound for Object."""
def play(O):
	f = sounds(O)
	# nvwave.set_volume(40/100)
	if cfgSounds and os.path.exists(f):
		nvwave.playWaveFile(f, 1)

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory= _("navigation sounds")
	def __init__(self, *args, **kwargs):
		globalPluginHandler.GlobalPlugin.__init__(self, *args, **kwargs)
		NVDASettingsDialog.categoryClasses.append(NavSettingsPanel)
		global old
		old = speech.speech.getPropertiesSpeech
	def play1(self,l):
		if os.path.exists(os.path.join(loc1(),os.listdir(loc1())[0])) and config.conf[roleSECTION]["typing"]:
			nvwave.playWaveFile(os.path.join(loc1(),choice(os.listdir(loc1()))),1)
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
		if not sayStates or not sayRoles:
			speech.speech.getPropertiesSpeech = getSpeechTextForProperties2
		if(cfgSounds):
			STATES=[s for s in obj.states if os.path.exists(sounds(s))==True]
			if len(STATES)>0:
				for state in STATES:
					play(state);#break
			elif os.path.exists(sounds(obj.role)): play(obj.role);#break
		nextHandler()

	@script(gesture="kb:NVDA+alt+n")
	def script_toggle(self, gesture):
		global cfgSounds
		cfgTyping =config.conf[roleSECTION]["typing"]
		isSameScript = getLastScriptRepeatCount()
		if isSameScript == 0:
			cfgSounds = not cfgSounds
			if cfgSounds==False:
				ui.message(_("Disable navigation sounds"))
			else:
				ui.message(_("Enable navigation sounds"))
		elif isSameScript ==1:
			cfgTyping = not cfgTyping
			if cfgTyping ==False:
				ui.message(_("Disable typing sounds"))
			else:
				ui.message(_("Enable typing sounds"))
		config.conf[roleSECTION]["typing"] = cfgTyping
		config.conf[roleSECTION]["cfgSounds"] = cfgSounds
	script_toggle.__doc__= _("Pressing it once toggles between on and off object sounds, and Pressing twice  it toggles between on and off typing sounds.")
	def terminate(self):
		NVDASettingsDialog.categoryClasses.remove(NavSettingsPanel)

class NavSettingsPanel(SettingsPanel):
	title = _("navigation sounds")
	def makeSettings(self, settingsSizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.tlable = sHelper.addItem(wx.StaticText(self, label=_("select sound"), name="ts"))
		self.sou= sHelper.addItem(wx.Choice(self, name="ts"))
		self.sou.Set(os.listdir(os.path.join(mainPaths, "effects","navsounds")))
		self.sou.SetStringSelection(config.conf[roleSECTION]["soundType"])
		self.nar=sHelper.addItem(wx.CheckBox(self,label=_("say roles")))
		self.nar.SetValue(config.conf[roleSECTION]["sayRoles"])
		self.nas=sHelper.addItem(wx.CheckBox(self,label=_("say states")))
		self.nas.SetValue(config.conf[roleSECTION]["sayStates"])
		self.nab=sHelper.addItem(wx.CheckBox(self,label=_("navigation sounds")))
		self.nab.SetValue(config.conf[roleSECTION]["cfgSounds"])
		self.ts=sHelper.addItem(wx.CheckBox(self,label=_("keyboard typing sound")))
		self.ts.SetValue(config.conf[roleSECTION]["typing"])
		self.edit=sHelper.addItem(wx.CheckBox(self,label=_("enable typing sound in text boxes only")))
		self.edit.SetValue(config.conf[roleSECTION]["edit"])
		self.tlable1 = sHelper.addItem(wx.StaticText(self, label=_("select typing sound"), name="tt"))
		self.sou1= sHelper.addItem(wx.Choice(self, name="tt"))
		self.sou1.Set(os.listdir(os.path.join(mainPaths, "effects","typingsound")))
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
		global sayRoles,sayStates,cfgSounds ,sounds1 
		config.conf[roleSECTION]["soundType"]=self.sou.GetStringSelection()
		config.conf[roleSECTION]["sayRoles"]=self.nar.GetValue()
		sayRoles=config.conf[roleSECTION]["sayRoles"]
		config.conf[roleSECTION]["sayStates"]=self.nas.GetValue()
		sayStates=config.conf[roleSECTION]["sayStates"]
		config.conf[roleSECTION]["cfgSounds"]=self.nab.GetValue()
		cfgSounds=config.conf[roleSECTION]["cfgSounds"]
		config.conf[roleSECTION]["typing"]=self.ts.GetValue()
		config.conf[roleSECTION]["edit"]=self.edit.GetValue()
		config.conf[roleSECTION]["type"]=self.sou1.GetStringSelection()
		config.conf[roleSECTION]["volume"]=self.sou2.GetValue()
		sounds1={}
	def ondonate(self,e):
		ui.message("please wait")
		web.open("https://www.paypal.me/ahmedthebest31")
		ui.message("donation link is opened")
