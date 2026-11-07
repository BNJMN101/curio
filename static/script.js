const socket = io();

const appEl = document.getElementById('app');
const messagesEl = document.getElementById('messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const onlineEl = document.getElementById('online');

const myName = appEl.dataset.username;
let lastSender = null;

const COLORS = ['#e17076', '#faa774', '#a695e7', '#7bc862', '#6ec9cb', '#65aadd', '#ee7aae'];

function colorFor(name) {
  let hash = 0;
  for (const ch of name) {
    hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  }
  return COLORS[hash % COLORS.length];
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addSystem(text) {
  const div = document.createElement('div');
  div.className = 'system';
  div.textContent = text;
  messagesEl.appendChild(div);
  lastSender = null;
  scrollToBottom();
}

function addMessage({ user, text, time }) {
  const mine = user === myName;

  const row = document.createElement('div');
  row.className = 'row ' + (mine ? 'mine' : 'theirs');

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  if (!mine && user !== lastSender) {
    const nameEl = document.createElement('div');
    nameEl.className = 'name';
    nameEl.style.color = colorFor(user);
    nameEl.textContent = user;
    bubble.appendChild(nameEl);
  }

  const textEl = document.createElement('span');
  textEl.textContent = text;

  const timeEl = document.createElement('span');
  timeEl.className = 'time';
  timeEl.textContent = time;

  bubble.append(textEl, timeEl);
  row.appendChild(bubble);
  messagesEl.appendChild(row);

  lastSender = user;
  scrollToBottom();
}

function updateOnline(list) {
  onlineEl.textContent = list.length + ' online: ' + list.join(', ');
}

function send() {
  const text = messageInput.value.trim();
  if (!text) return;
  socket.emit('message', text);
  messageInput.value = '';
  messageInput.focus();
}

sendBtn.addEventListener('click', send);
messageInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });

socket.on('message', addMessage);
socket.on('system', addSystem);
socket.on('users', updateOnline);
socket.on('disconnect', () => addSystem('Connection lost. Refresh the page to reconnect.'));

messageInput.focus();