const { WebcastPushConnection } = require('tiktok-live-connector');
const WebSocket = require('ws');

const tiktokUsername = 'therealnucax';
const wss = new WebSocket.Server({ port: 8080 });

wss.on('connection', ws => {
    console.log('Conectado al bot de Python');
});

let tiktokLiveConnection = new WebcastPushConnection(tiktokUsername);

tiktokLiveConnection.connect().then(state => {
    console.log('Conectado a TikTok Live');
}).catch(err => {
    console.error('Error al conectar:', err);
});

tiktokLiveConnection.on('chat', data => {
    const message = `${data.nickname} dijo: ${data.comment}`;
    console.log(message);
    wss.clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(JSON.stringify({ message }));
        }
    });
});