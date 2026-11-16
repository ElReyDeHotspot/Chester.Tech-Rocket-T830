const fs = require('fs');
const path = require('path');
const assert = require('assert');
const source = fs.readFileSync(path.join(__dirname, '../firmware-overlay/www/luci-static/resources/view/chester-ota/index.js'), 'utf8');
String.prototype.format = function(...args) { let i = 0; return this.replace(/%s/g, () => String(args[i++])); };
const calls = [], modals = [], notifications = [], polls = [];
const E = (tag, props, children) => ({tag, props: props || {}, children: children || [], checked: !!(props && props.checked), textContent: '', disabled: false});
const api = {
  exec: async (command, args) => {
    assert.strictEqual(command, '/usr/sbin/chester-ota'); calls.push(args);
    const value = args[0] === 'settings' ? {keep_settings: true, auto_update: false, installed_sequence: '1'}
      : args[0] === 'status' ? {phase: 'idle', message: 'Idle'}
      : args[0] === 'check' ? {release: {version: '2026.11.16.1'}}
      : args[0] === 'queue' ? {queued: true} : {ok: true};
    return {code: 0, stdout: JSON.stringify(value)};
  }
};
const ui = {
  showModal: (title, body) => modals.push({title, body}), hideModal() {}, awaitReconnect() {},
  createHandlerFn: (self, fn) => (...args) => typeof fn === 'string' ? self[fn](...args) : fn.apply(self, args)
};
const misectel = {
  ensureBaseStyle() {}, setButtonBusy(button, flag) {button.disabled = flag;}, notify: (...args) => notifications.push(args),
  createButton: (label, css, click) => ({label, click, disabled: false}),
  createCard: (title, text, children) => ({title, text, children}),
  createField: (label, control, description) => ({label, control, description}),
  createInlineCheck: (input, label) => ({input, label})
};
const view = new Function('view', 'fs', 'ui', 'poll', 'misectel', 'E', '_', 'window', source)(
  {extend: obj => obj}, api, ui, {add: fn => polls.push(fn)}, misectel, E, x => x, {location: {host: '192.168.100.1'}});
(async () => {
  const data = await view.load(); view.render(data);
  assert.strictEqual(view.keep.checked, true); assert.strictEqual(view.automatic.checked, false);
  view.keep.checked = false; view.automatic.checked = true;
  await view.handleSavePreferences({});
  assert.deepStrictEqual(calls.at(-1), ['configure', '0', '1']);
  await view.handleCheck({}); assert.strictEqual(view.install.disabled, false);
  view.handleInstall(); assert.strictEqual(calls.filter(x => x[0] === 'queue').length, 0);
  assert.ok(JSON.stringify(modals.at(-1)).includes('return to factory defaults'));
  const buttons = modals.at(-1).body.at(-1).children;
  buttons[1].click(); await new Promise(resolve => setImmediate(resolve));
  assert.deepStrictEqual(calls.slice(-2), [['configure', '0', '1'], ['queue']]);
  assert.strictEqual(view.reconnectHost, '192.168.100.1');
  console.log('UI checks passed: defaults, toggle persistence, update check, reset warning, confirmation gate, queue and reconnect.');
})().catch(error => { console.error(error); process.exit(1); });
