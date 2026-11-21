/* Standalone stand-in for Ondelette's shared/account.js.
 *
 * Plugged into Ondelette, the page loads Ondelette's own account.js at this address: signing in,
 * the profile menu, the account settings. Served by serve.py there are no accounts: one local
 * user, said by the server (auth/me). Served as plain files nothing answers: 'static'.
 * The page only relies on `start` and on its three outcomes. */
(function (OND) {
  'use strict';
  const state = { mode: 'unknown', user: null };
  async function start(o) {
    try {
      const session = await OND.api.get('auth/me', { quiet: true });
      state.user = session.user; state.mode = 'user';
      if (o && o.slot) o.slot.hidden = true;
      if (o && o.onUser) o.onUser(state.user);
    } catch (e) { state.mode = 'static'; }
    return state.mode;
  }
  OND.account = { state, start, signOut: () => {}, openSettings: () => {}, openUsers: () => {} };
})(window.OND);
