'use strict';
'require view';
'require fs';
'require ui';
'require poll';
'require misectel.ui as misectel';

function execute(args) {
	return fs.exec('/usr/sbin/chester-ota', args).then(function(result) {
		if (result.code !== 0)
			throw new Error((result.stderr || result.stdout || _('Update service failed.')).trim());
		try { return JSON.parse(result.stdout); }
		catch (err) { throw new Error(_('The update service returned an unreadable response.')); }
	});
}

return view.extend({
	load: function() {
		misectel.ensureBaseStyle();
		return Promise.all([execute(['settings']), execute(['status'])]);
	},
	savePreferences: function() {
		return execute(['configure', this.keep.checked ? '1' : '0', this.automatic.checked ? '1' : '0']);
	},
	handleSavePreferences: function(button) {
		misectel.setButtonBusy(button, true);
		return this.savePreferences().then(function() {
			misectel.notify(_('Update preferences saved.'), 'success');
		}).catch(function(err) {
			misectel.notify(err.message, 'error');
		}).finally(function() { misectel.setButtonBusy(button, false); });
	},
	handleCheck: function(button) {
		var self = this;
		misectel.setButtonBusy(button, true);
		return execute(['check']).then(function(manifest) {
			self.manifest = manifest;
			self.release.textContent = _('Available version: %s').format(manifest.release.version);
			self.install.disabled = false;
		}).catch(function(err) {
			self.manifest = null;
			self.install.disabled = true;
			self.release.textContent = err.message;
		}).finally(function() { misectel.setButtonBusy(button, false); });
	},
	handleInstall: function() {
		if (!this.manifest) return;
		var self = this;
		var keep = this.keep.checked;
		ui.showModal(_('Install firmware update'), [
			E('p', {}, _('Install version %s and restart the router?').format(this.manifest.release.version)),
			E('p', { 'class': keep ? 'misectel-notice' : 'alert-message warning' }, keep
				? _('Your saved router settings will be retained.')
				: _('Retain data is off. Wi-Fi, LAN, APN and administrator settings will return to factory defaults.')),
			E('p', {}, _('Do not disconnect power during installation.')),
			E('div', { 'class': 'misectel-card__footer' }, [
				misectel.createButton(_('Cancel'), 'misectel-button-secondary', ui.hideModal),
				misectel.createButton(_('Install update'), 'misectel-button', function() {
					ui.hideModal();
					self.install.disabled = true;
					self.savePreferences().then(function() { return execute(['queue']); }).then(function() {
						self.job.textContent = _('Update queued. Checking and downloading firmware...');
						self.reconnectHost = keep ? window.location.host : '192.168.100.1';
					}).catch(function(err) {
						self.install.disabled = false;
						misectel.notify(err.message, 'error');
					});
				})
			])
		]);
	},
	render: function(data) {
		var self = this;
		var settings = data[0];
		this.keep = E('input', { type: 'checkbox', checked: settings.keep_settings ? 'checked' : null });
		this.automatic = E('input', { type: 'checkbox', checked: settings.auto_update ? 'checked' : null });
		this.release = E('p', { 'class': 'misectel-notice' }, _('Check for a newer signed stable release.'));
		this.job = E('p', { 'class': 'misectel-notice' }, data[1].message || _('No update is running.'));
		this.install = misectel.createButton(_('Install update'), 'misectel-button', ui.createHandlerFn(this, 'handleInstall'));
		this.install.disabled = true;
		var check = misectel.createButton(_('Check for updates'), 'misectel-button-secondary', function(ev) { return self.handleCheck(ev.currentTarget); });
		var save = misectel.createButton(_('Save preferences'), 'misectel-button', function(ev) { return self.handleSavePreferences(ev.currentTarget); });
		poll.add(function() {
			return execute(['status']).then(function(state) {
				self.job.textContent = state.message;
				var active = ['queued', 'checking', 'downloading', 'validating', 'installing'].indexOf(state.phase) >= 0;
				check.disabled = active;
				self.install.disabled = active || !self.manifest;
				if (state.phase === 'installing' && !self.reconnecting) {
					self.reconnecting = true;
					ui.showModal(_('Installing firmware'), [E('p', { 'class': 'spinning' }, _('The router will restart. Do not disconnect power.'))]);
					ui.awaitReconnect(self.reconnectHost || (self.keep.checked ? window.location.host : '192.168.100.1'));
				}
			}).catch(function() { /* A reboot temporarily closes the management connection. */ });
		}, 3);
		return E('div', { 'class': 'misectel-page' }, [E('div', { 'class': 'misectel-shell' }, [
			misectel.createCard(_('System Update'), _('Signed firmware updates for Chester.Tech Rocket T830.'), [
				E('p', {}, _('Installed update sequence: %s').format(settings.installed_sequence)),
				E('div', { 'class': 'misectel-form-grid' }, [
					misectel.createField(_('Retain data'), misectel.createInlineCheck(this.keep, _('Keep router settings')), _('Preserve Wi-Fi, LAN, APN, administrator and updater settings. Extra installed applications may need reinstalling.')),
					misectel.createField(_('Auto update'), misectel.createInlineCheck(this.automatic, _('Enable automatic updates')), _('Check every six hours and install newer verified stable firmware automatically. The router will restart.'))
				]),
				E('div', { 'class': 'misectel-card__footer' }, [save]),
				this.release, this.job,
				E('div', { 'class': 'misectel-card__footer' }, [check, this.install])
			])
		])]);
	},
	handleSave: null,
	handleSaveApply: null,
	handleReset: null
});
