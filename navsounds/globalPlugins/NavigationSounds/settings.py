import os
from datetime import date
from pathlib import Path
from typing import Any, Callable
import webbrowser as web

import wx

import addonHandler
from gui import guiHelper
from gui.settingsDialogs import SettingsPanel
from logHandler import log
import ui

from .theme_import import (
	NAV_KIND,
	TYPE_KIND,
	ThemeImportError,
	get_user_themes_root,
	import_theme_zip,
	list_user_themes,
	read_archive_wav_stems,
	set_translator,
)

addonHandler.initTranslation()
_: Callable[[str], str]
set_translator(_)

# Curated sound packs, served as static files and updated by hand. Kept as a
# single constant so a future domain change stays one edit. The add-on only
# opens a browser; it never talks to the network itself.
STORE_URL = "https://ahmedthebest31.github.io/navsounds/store/"

# Both donation pages are plain web pages handed to the browser, exactly like
# the store link.
PAYPAL_URL = "https://www.paypal.me/ahmedthebest31"
INSTAPAY_URL = "https://ipn.eg/S/ahmedsamyelkhouly/instapay/1KWwcR"

# How often the startup reminder may come back. Thirty days keeps it present
# through a release cycle without turning into nagging, and the user can switch
# it off permanently from the dialog itself.
DONATION_PROMPT_INTERVAL_DAYS = 30

# Order must match the choices offered by the theme type dialog.
KIND_CHOICES = (NAV_KIND, TYPE_KIND)


def should_prompt_for_donation(
	enabled: bool,
	last_shown: str,
	today: date,
	interval_days: int = DONATION_PROMPT_INTERVAL_DAYS,
) -> bool:
	"""Whether the startup donation reminder is due.

	Kept free of wx and of NVDA imports so the schedule can be tested directly.
	A damaged stored date is treated as "never shown" rather than silently
	suppressing the reminder forever.
	"""
	if not enabled:
		return False
	if not last_shown:
		return True
	try:
		previous = date.fromisoformat(last_shown)
	except ValueError:
		return True
	return (today - previous).days >= interval_days


class NavSettingsPanel(SettingsPanel):
	main_plugin: Any
	title = _("navigation sounds")

	def makeSettings(self, sizer: wx.Sizer) -> None:
		if self.main_plugin is None:
			raise ValueError("The plugin is not transferred to the settings panel")

		nav_sounds = self._theme_choices(NAV_KIND)
		type_sounds = self._theme_choices(TYPE_KIND)

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

		store_buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		open_store = store_buttons.addButton(self, label=_("open theme store"), name="store")
		open_store.Bind(wx.EVT_BUTTON, self.onopenstore)
		import_theme = store_buttons.addButton(self, label=_("import sound theme..."), name="import")
		import_theme.Bind(wx.EVT_BUTTON, self.onimporttheme)
		sizer_helper.addItem(store_buttons)

		folder_buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		open_themes = folder_buttons.addButton(self, label=_("open themes folder"), name="themes")
		open_themes.Bind(wx.EVT_BUTTON, self.onopenthemes)
		open_bundled = folder_buttons.addButton(self, label=_("open bundled sounds folder"), name="bundled")
		open_bundled.Bind(wx.EVT_BUTTON, self.onopen)
		sizer_helper.addItem(folder_buttons)

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

	def onopenthemes(self, evt: wx.Event) -> None:
		# Created on demand, so the very first press is useful instead of failing
		# on a path that does not exist yet for a user who never imported a pack.
		themes_path = get_user_themes_root(self.main_plugin.config_path)
		try:
			themes_path.mkdir(parents=True, exist_ok=True)
			os.startfile(themes_path)
		except OSError as error:
			log.warning(f"Could not open the themes folder: {error}")
			ui.message(_("the themes folder could not be opened"))
			return
		ui.message(_("the themes folder is opened, your imported themes are inside it"))

	def onopen(self, evt: wx.Event) -> None:
		effects_path = Path(__file__).resolve().parent / "effects"
		try:
			os.startfile(effects_path)
		except OSError as error:
			log.warning(f"Could not open the bundled effects folder: {error}")
			ui.message(_("the bundled sounds folder could not be opened"))
			return
		ui.message(_("the bundled sounds folder is opened"))

	def onopenstore(self, evt: wx.Event) -> None:
		# Same mechanism as the donate button: hand the URL to the browser and
		# say so, rather than silently doing nothing when no browser is found.
		if web.open(STORE_URL):
			ui.message(_("the theme store is opened in your web browser"))
		else:
			ui.message(_("the theme store could not be opened, visit {}").format(STORE_URL))

	def onimporttheme(self, evt: wx.Event) -> None:
		with wx.FileDialog(
			self,
			_("open sound theme archive"),
			wildcard=_("theme archives") + " (*.zip)|*.zip",
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		) as dlg:
			if dlg.ShowModal() != wx.ID_OK:
				return
			archive = Path(dlg.GetPath())

		kind = self._ask_theme_kind(archive)
		if kind is None:
			return

		try:
			result = import_theme_zip(
				archive,
				self.main_plugin.config_path,
				kind,
				self._builtin_theme_names(kind),
			)
		except ThemeImportError as error:
			ui.message(_("the theme could not be imported: {}").format(error), errorLevel=1)
			return

		self._select_theme(kind, result.theme_name)
		message = _("theme '{}' was imported with {} sound files").format(result.theme_name, result.file_count)
		if result.skipped_count:
			message = _("{} {}").format(message, _("{} unusable file was skipped.").format(result.skipped_count))
		ui.message(message)

	def _ask_theme_kind(self, archive: Path) -> str | None:
		"""Ask which sound category to install into, defaulting to a guess.

		Navigation packs name their files after controlTypes roles and typing
		packs do not, which makes the guess reliable. It stays only a default:
		the user always decides, so an unusual pack can still be filed properly.
		"""
		labels = [_("navigation sounds (roles and states)"), _("typing sounds (keyboard)")]
		with wx.Dialog(self, title=_("theme type")) as dlg:
			sizer = guiHelper.BoxSizerHelper(dlg, orientation=wx.VERTICAL)
			sizer.addItem(wx.StaticText(dlg, label=_("which sounds does '{}' contain?").format(archive.name)))
			radio = wx.RadioBox(
				dlg,
				label=_("theme type"),
				choices=labels,
				majorDimension=1,
				style=wx.RA_SPECIFY_ROWS,
			)
			sizer.addItem(radio)
			sizer.addDialogDismissButtons(wx.OK | wx.CANCEL)
			dlg.SetSizer(sizer.sizer)
			dlg.Fit()
			dlg.CenterOnParent()
			if self._guess_theme_kind(archive) == TYPE_KIND:
				radio.SetSelection(1)
			if dlg.ShowModal() != wx.ID_OK:
				return None
			index = radio.GetSelection()
		return KIND_CHOICES[index] if index in (0, 1) else NAV_KIND

	def _guess_theme_kind(self, archive: Path) -> str | None:
		"""Guess the sound category from the wav names inside the archive.

		Navigation packs name their files after controlTypes roles and typing
		packs do not, so wavs without any role name point at the keyboard.
		Only an unreadable archive gives no guess at all.
		"""
		try:
			stems = read_archive_wav_stems(archive)
		except ThemeImportError:
			return None
		if not stems:
			return None
		if any(self.main_plugin.is_role_sound_name(stem) for stem in stems):
			return NAV_KIND
		return TYPE_KIND

	def _builtin_theme_names(self, kind: str) -> list[str]:
		"""Names of the themes shipped inside the add-on."""
		kind_dir = self.main_plugin.main_paths / "effects" / kind
		if not kind_dir.is_dir():
			return []
		return [entry.name for entry in kind_dir.iterdir() if entry.is_dir()]

	def _theme_choices(self, kind: str) -> list[str]:
		"""Bundled themes first, then imported ones, without duplicates.

		Each group is sorted on its own, so the shipped packs keep their block at
		the top of the list and an import is only ever appended below them.
		"""
		bundled = sorted(self._builtin_theme_names(kind), key=str.casefold)
		# Never let the imported list break the panel: NVDA freezes its scrolled
		# settings container while a category is being built and only Thaws it if
		# the build succeeds, so one exception here would leave the dialog frozen
		# and overlapping the previously shown category for the whole session.
		try:
			imported = sorted(list_user_themes(self.main_plugin.config_path, kind), key=str.casefold)
		except (OSError, ThemeImportError) as error:
			log.warning(f"Could not list imported {kind} themes: {error}")
			imported = []
		names: list[str] = []
		seen: set[str] = set()
		for name in bundled + imported:
			key = name.casefold()
			if key in seen:
				continue
			seen.add(key)
			names.append(name)
		return names

	def _select_theme(self, kind: str, theme_name: str) -> None:
		"""Rebuild one dropdown so a fresh import is selectable straight away.

		The sound cache is deliberately left alone: onSave already reloads it
		when the selection really changes, which keeps one import to one decode
		pass instead of two.
		"""
		choice = self.sou if kind == NAV_KIND else self.sou1
		previous = choice.GetStringSelection()
		choice.Set(self._theme_choices(kind))
		choice.SetStringSelection(theme_name if theme_name in choice.GetItems() else previous)
		self.Layout()

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

	def ondonate(self, evt: wx.Event) -> None:
		show_donate_dialog(self, first_run=False)


class DonateDialog(wx.Dialog):
	"""Asks how the user wants to donate.

	`first_run` is the variant shown after install: it carries the message about
	the work that went into the add-on and a checkbox that stops the reminder.
	"""

	def __init__(self, parent: Any, first_run: bool = False) -> None:
		super().__init__(parent, title=_("support navSounds development"), style=wx.DEFAULT_DIALOG_STYLE)
		if first_run:
			message = _(
				"navSounds is free, and it always will be. A lot of work went into keeping it fast, "
				"light and reliable on every device, including yours. If you like it, a small "
				"donation helps that work continue."
			)
		else:
			message = _("choose how you would like to donate")

		self.choice = ""
		self.dont_ask: Any = None

		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(self, label=message), flag=wx.ALL | wx.EXPAND, border=16)
		if first_run:
			self.dont_ask = wx.CheckBox(self, label=_("do not show this again"))
			sizer.Add(self.dont_ask, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=16)
		buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		paypal = buttons.addButton(self, label=_("donate with PayPal"), name="paypal")
		paypal.Bind(wx.EVT_BUTTON, self.onChoosePayPal)
		instapay = buttons.addButton(self, label=_("donate with InstaPay Egypt"), name="instapay")
		instapay.Bind(wx.EVT_BUTTON, self.onChooseInstaPay)
		# Escape and the close button mean "not now", never an accidental donation.
		sizer.Add(buttons, flag=wx.ALL | wx.EXPAND, border=16)
		sizer.Add(wx.Button(self, wx.ID_CANCEL, _("close")), flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=16)
		self.SetSizerAndFit(sizer)
		paypal.SetFocus()

	def onChoosePayPal(self, evt: wx.Event) -> None:
		self.choice = PAYPAL_URL
		self.EndModal(wx.ID_OK)

	def onChooseInstaPay(self, evt: wx.Event) -> None:
		self.choice = INSTAPAY_URL
		self.EndModal(wx.ID_OK)


def show_donate_dialog(parent: Any, first_run: bool = False) -> bool:
	"""Opens the donation dialog and returns True if the reminder was switched off."""
	result = wx.ID_CANCEL
	choice = ""
	disable = False
	try:
		with DonateDialog(parent, first_run) as dialog:
			result = dialog.ShowModal()
			choice = dialog.choice
			checkbox = dialog.dont_ask
			disable = bool(checkbox is not None and checkbox.GetValue())
	except Exception:
		log.exception("The donation dialog could not be shown")
		return False
	if result != wx.ID_OK or not choice:
		return disable
	if not web.open(choice):
		ui.message(_("the donation page could not be opened"))
		return disable
	ui.message(_("the donation page is opened in your web browser"))
	return disable
