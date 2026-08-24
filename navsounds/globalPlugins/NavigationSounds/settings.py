import os
from pathlib import Path
from typing import Any, Callable
import webbrowser as web

import wx

import addonHandler
from gui import guiHelper
from gui.settingsDialogs import SettingsPanel
import ui

addonHandler.initTranslation()
_: Callable[[str], str]


class NavSettingsPanel(SettingsPanel):
	main_plugin: Any
	title = _("navigation sounds")

	def makeSettings(self, sizer: wx.Sizer) -> None:
		if self.main_plugin is None:
			raise ValueError("The plugin is not transferred to the settings panel")

		base_sounds_dir = self.main_plugin.main_paths / "effects"
		nav_sounds_dir = base_sounds_dir / "navsounds"
		type_sounds_dir = base_sounds_dir / "typingsound"

		nav_sounds = [p.name for p in nav_sounds_dir.iterdir() if p.is_dir()] if nav_sounds_dir.is_dir() else []
		type_sounds = [p.name for p in type_sounds_dir.iterdir() if p.is_dir()] if type_sounds_dir.is_dir() else []

		sizer_helper = guiHelper.BoxSizerHelper(self, sizer=sizer)

		sizer_helper.addItem(wx.StaticText(self, label=_("select sound"), name="ts"))
		self.sou = sizer_helper.addItem(wx.Choice(self, name="ts"))
		self.sou.Set(nav_sounds)
		self.sou.SetStringSelection(self.main_plugin.role_section["soundType"])

		self.nar = sizer_helper.addItem(wx.CheckBox(self, label=_("say element roles")))
		self.nar.SetValue(self.main_plugin.role_section["sayRoles"])

		self.nas = sizer_helper.addItem(wx.CheckBox(self, label=_("say element states")))
		self.nas.SetValue(self.main_plugin.role_section["sayStates"])

		self.nab = sizer_helper.addItem(wx.CheckBox(self, label=_("navigation sounds")))
		self.nab.SetValue(self.main_plugin.role_section["cfgSounds"])

		self.mouse_cb = sizer_helper.addItem(wx.CheckBox(self, label=_("play sounds on mouse hover")))
		self.mouse_cb.SetValue(self.main_plugin.role_section.get("mouseSounds", False))
		self.mouse_cb.Bind(wx.EVT_CHECKBOX, self.on_mouse_cb_change)

		self.mouse_delay_label = wx.StaticText(self, label=_("mouse hover delay (ms)"), name="mdl")
		sizer_helper.addItem(self.mouse_delay_label)
		self.mouse_delay_ctrl = sizer_helper.addItem(wx.SpinCtrl(self, name="mdl", min=50, max=2000))
		self.mouse_delay_ctrl.SetValue(self.main_plugin.role_section.get("mouseHoverDelay", 50))

		is_mouse_enabled = self.mouse_cb.GetValue()
		self.mouse_delay_label.Enable(is_mouse_enabled)
		self.mouse_delay_ctrl.Enable(is_mouse_enabled)

		self.ts = sizer_helper.addItem(wx.CheckBox(self, label=_("keyboard typing sound")))
		self.ts.SetValue(self.main_plugin.role_section["typing"])
		self.ts.Bind(wx.EVT_CHECKBOX, self.on_typing_cb_change)

		self.edit = sizer_helper.addItem(wx.CheckBox(self, label=_("enable typing sound in text boxes only")))
		self.edit.SetValue(self.main_plugin.role_section["edit"])

		self.tt_label = wx.StaticText(self, label=_("select typing sound"), name="tt")
		sizer_helper.addItem(self.tt_label)
		self.sou1 = sizer_helper.addItem(wx.Choice(self, name="tt"))
		self.sou1.Set(type_sounds)
		self.sou1.SetStringSelection(self.main_plugin.role_section["type"])

		is_typing_enabled = self.ts.GetValue()
		self.edit.Show(is_typing_enabled)
		self.tt_label.Show(is_typing_enabled)
		self.sou1.Show(is_typing_enabled)

		self.arrow_nav_cb = sizer_helper.addItem(
			wx.CheckBox(self, label=_("play navigation sounds during arrow key navigation"))
		)
		self.arrow_nav_cb.SetValue(self.main_plugin.role_section.get("arrowNavSounds", True))

		sizer_helper.addItem(wx.StaticText(self, label=_("volume"), name="tt3"))
		self.sou3 = sizer_helper.addItem(
			wx.Slider(
				self,
				name="tt3",
				value=self.main_plugin.role_section["volume"],
				minValue=0,
				maxValue=100,
				style=wx.SL_HORIZONTAL,
			)
		)

		b = sizer_helper.addItem(wx.Button(self, label=_("open sounds folder")))
		b.Bind(wx.EVT_BUTTON, self.onopen)

		donate = sizer_helper.addItem(wx.Button(self, label=_("donate")))
		donate.Bind(wx.EVT_BUTTON, self.ondonate)

	def postInit(self) -> None:
		self.sou.SetFocus()

	def on_typing_cb_change(self, evt: wx.Event) -> None:
		is_enabled = self.ts.GetValue()
		self.edit.Show(is_enabled)
		self.tt_label.Show(is_enabled)
		self.sou1.Show(is_enabled)
		self.Layout()
		evt.Skip()

	def on_mouse_cb_change(self, evt: wx.Event) -> None:
		is_enabled = self.mouse_cb.GetValue()
		self.mouse_delay_label.Enable(is_enabled)
		self.mouse_delay_ctrl.Enable(is_enabled)
		evt.Skip()

	def onopen(self, _: wx.Event) -> None:
		effects_path = Path(__file__).resolve().parent / "effects"
		os.startfile(effects_path)

	def onSave(self) -> None:
		if self.main_plugin is None:
			raise ValueError("The plugin is not transferred to the settings panel")

		# Capture previous values first so only real changes trigger a reload.
		old_volume = self.main_plugin.role_section["volume"]
		old_sound_type = self.main_plugin.role_section["soundType"]
		old_typing_type = self.main_plugin.role_section["type"]

		new_volume = self.sou3.GetValue()
		new_sound_type = self.sou.GetStringSelection()
		new_typing_type = self.sou1.GetStringSelection()

		self.main_plugin.role_section["soundType"] = new_sound_type

		self.main_plugin.role_section["sayRoles"] = self.nar.GetValue()
		self.main_plugin.say_roles = self.main_plugin.role_section["sayRoles"]

		self.main_plugin.role_section["sayStates"] = self.nas.GetValue()
		self.main_plugin.say_states = self.main_plugin.role_section["sayStates"]

		self.main_plugin.role_section["cfgSounds"] = self.nab.GetValue()
		self.main_plugin.cfg_sounds = self.main_plugin.role_section["cfgSounds"]
		if self.main_plugin.cfg_sounds:
			self.main_plugin.browser_interceptor.patch()
		else:
			self.main_plugin.browser_interceptor.terminate()

		self.main_plugin.role_section["mouseSounds"] = self.mouse_cb.GetValue()
		self.main_plugin.role_section["mouseHoverDelay"] = self.mouse_delay_ctrl.GetValue()

		self.main_plugin.role_section["typing"] = self.ts.GetValue()
		self.main_plugin.role_section["edit"] = self.edit.GetValue()

		self.main_plugin.role_section["type"] = new_typing_type

		self.main_plugin.role_section["arrowNavSounds"] = self.arrow_nav_cb.GetValue()

		self.main_plugin.role_section["volume"] = new_volume

		if new_volume != old_volume:
			self.main_plugin.audio_manager.update_volume(new_volume)

		if new_volume != old_volume or new_sound_type != old_sound_type or new_typing_type != old_typing_type:
			self.main_plugin.reload_audio()

	def ondonate(self, _: wx.Event) -> None:
		ui.message(_("please wait"))
		web.open("https://www.paypal.me/ahmedthebest31")
		ui.message(_("donation link is opened"))
