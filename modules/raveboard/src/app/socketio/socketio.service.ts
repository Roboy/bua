import { Injectable } from "@angular/core";
import { Subject } from "rxjs";
import * as io from "socket.io-client";

import { ActivationUpdate } from "../model/activation-update";
import { SpikeUpdate } from "../model/spike-update";
import { MessageToUI } from "../model/message-to-ui";
import { MessageFromUI } from "../model/message-from-ui";


@Injectable({
    providedIn: 'root'
})
export class SocketIOService {

    // inputs: subscribe to receive messages
    activations: Subject<ActivationUpdate> = new Subject();
    spikes: Subject<SpikeUpdate> = new Subject();
    messagesToUI: Subject<MessageToUI> = new Subject();

    // output: call emit() to send a message
    messagesFromUI: Subject<MessageFromUI> = new Subject();

    constructor() {
        const urlParams = new URLSearchParams(window.location.search);
        const sioUrl = urlParams.get('rs-sio-url') || 'http://localhost:42424';
        const token = urlParams.get('token') || '';

        console.log(`Connecting to socket.io URL: '${sioUrl}'`);

        let socket = io.connect(sioUrl, {query: {token: token}});

        socket.on('spike', msg => {
            this.spikes.next(msg)
        });

        socket.on('activation', msg => {
            this.activations.next(msg)
        });

        socket.on('output', msg => {
            this.messagesToUI.next(msg);
        });

        // listen for messages emitted by UI and send to the server
        this.messagesFromUI.subscribe(msg => { // no unsubscribe since this service lives forever
            socket.emit('input', msg);
        });
    }

    sendMessage(message: string) {
        this.messagesFromUI.next({
            type: 'input',
            text: message
        });
    }

}
