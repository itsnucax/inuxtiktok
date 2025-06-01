"use strict";

var _require = require('tiktok-live-connector'),
    WebcastPushConnection = _require.WebcastPushConnection;

var WebSocket = require('ws');

var tiktokUsername = 'therealnucax';
var wss = new WebSocket.Server({
  port: 8080
});
wss.on('connection', function (ws) {
  console.log('Conectado al bot de Python');
});
var tiktokLiveConnection = new WebcastPushConnection(tiktokUsername);
tiktokLiveConnection.connect().then(function (state) {
  console.log('Conectado a TikTok Live');
})["catch"](function (err) {
  console.error('Error al conectar:', err);
});
tiktokLiveConnection.on('chat', function (data) {
  var message = "".concat(data.nickname, " dijo: ").concat(data.comment);
  console.log(message);
  wss.clients.forEach(function (client) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify({
        message: message
      }));
    }
  });
});
//# sourceMappingURL=tiktok.dev.js.map
