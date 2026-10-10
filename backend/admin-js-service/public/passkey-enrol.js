// Passkey enrolment page (served at <admin root>/passkeys/enrol).
//
// The one-time token is in the URL fragment (#token=...), which the browser
// never sends to a server. It is read, then removed from the address bar so it
// does not linger in history.
(() => {
  const form = document.getElementById('enrol');
  const button = document.getElementById('submit');
  const status = document.getElementById('status');
  const token = new URLSearchParams(window.location.hash.slice(1)).get('token');
  history.replaceState(null, '', window.location.pathname);
  // This page is <root>/passkeys/enrol; its API is <root>/passkeys/enrol/{options,verify}.
  const base = window.location.pathname.replace(/\/$/, '');

  const say = (text, kind) => {
    status.textContent = text;
    status.className = kind || '';
  };

  const post = async (path, body) => {
    const response = await fetch(`${base}/${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(body),
    });
    const json = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(json.detail || `Request failed (${response.status})`);
    return json;
  };

  if (!token) {
    say('This link has no enrolment token. Ask the owner for a new link.', 'error');
    button.disabled = true;
    return;
  }
  if (typeof PublicKeyCredential === 'undefined' || typeof PublicKeyCredential.parseCreationOptionsFromJSON !== 'function') {
    say('This browser does not support passkeys. Use a current Chrome, Safari, Edge or Firefox.', 'error');
    button.disabled = true;
    return;
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const name = document.getElementById('name').value.trim();
    if (!name) return;
    button.disabled = true;
    say('Waiting for your device…');
    try {
      const started = await post('options', { token });
      const publicKey = PublicKeyCredential.parseCreationOptionsFromJSON(started.options);
      const credential = await navigator.credentials.create({ publicKey });
      await post('verify', { token, challengeId: started.challengeId, credential: credential.toJSON(), name });
      form.hidden = true;
      say('Passkey registered. You can now sign in to the admin panel with your password and this passkey.', 'ok');
    } catch (error) {
      button.disabled = false;
      say(error.name === 'NotAllowedError' ? 'The passkey prompt was cancelled or timed out.' : error.message, 'error');
    }
  });
})();
