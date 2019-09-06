import { Injectable } from '@angular/core';
import { Observable, Subject } from 'rxjs';
import { filter, map } from 'rxjs/operators';
import {webSocket} from "rxjs/webSocket";

export interface ActivationsTick {
    type: 'tick';
    activations: Array<{
        activated: boolean,
        constrains: {[name: string]: number},
        id: number,
        name: string,
        specificity: number
    }>;
}

export interface Spike {
    type: 'spike';
    id: number;
    name: string;
    parent: number;
    propertyValueAtCreation: any;
}


export interface SpikeUpdate {
    type: 'spike';

    /** (int) Identifies a unique spike - use to update view model. Can conflict with ActivationUpdate. */
    id: number;

    /** Signal represented by spike - use as caption. */
    signal: string;

    /** List of immediate parent spikes that caused this spike - draw connections pointing from parents to child spikes. */
    parents: Array<number>;
}

export interface ActivationUpdate {
    type: 'activation';

    /** (int) Identifies a unique activation - use to update view model. Can conflict with SpikeUpdate. */
    id: number;

    /** State represented by activation - use as caption. */
    state: string;

    /** (float) Specificity of state - visualise proportionally as relevance. */
    specificity: number;

    /**
     * Status of activation. Explanation:
     * - 'wait': Activation is waiting for additional spikes
     * - 'ready': Activation is waiting for permission to run
     * - 'run': Activation is executing
     */
    status: 'wait' | 'ready' | 'run';

    /**
     * Every map represents a disjunct conjunction of signal spike references as a map from signal name to spike ID.
     * A spike id of -1 indicates, that no spike for the given signal name is referenced yet.
     * An activation should only be displayed, if it references at least one spike.
     * Visualise referenced spikes as lines from the activation to the spike.
     */
    spikes: Array<{[signalName: string]: number}>;
}

const MOCK_MESSAGES: Array<SpikeUpdate | ActivationUpdate> = [
    // Message 0: A spike (id 0) is instantiated
    {
        type: 'spike',
        signal: 'rawio:in:changed',
        id: 0,
        parents: []
    },
    // Messages 1-3: Activations are introduced which reference the new spike
    {
        type: 'activation',
        id: 0,
        state: 'wildtalk',
        specificity: 0.2,
        status: 'ready',
        spikes: [{
            'rawio:in:changed': 0
        }]
    },
    {
        type: 'activation',
        id: 1,
        state: 'nlp',
        status: 'ready',
        specificity: 0.2,
        spikes: [{
            'rawio:in:changed': 0
        }]
    },
    {
        type: 'activation',
        id: 2,
        state: 'dinosaur-qa',
        status: 'wait',
        specificity: 1.2,
        spikes: [{
            'rawio:in:changed': 0,
            'nlp:is-question': -1,
            'visonio:is-dino': -1,
            'visonio:in:changed': -1
        }]
    },
    // Message 4: NLP state activation runs
    {
        type: 'activation',
        id: 1,
        state: 'nlp',
        specificity: 0.2,
        status: 'run',
        spikes: [{
            'rawio:in:changed': 0
        }]
    },
    // Message 5: NLP activation dereferences spikes
    {
        type: 'activation',
        id: 1,
        state: 'nlp',
        status: 'ready',
        specificity: 0.2,
        spikes: [{
            'rawio:in:changed': -1
        }]
    },
    // Message 6: nlp:is-question spike
    {
        type: 'spike',
        signal: 'nlp:is-question',
        id: 1,
        parents: [0]
    },
    // Message 7: dinosaur-qa refs. nlp:is-question
    {
        type: 'activation',
        id: 2,
        state: 'dinosaur-qa',
        status: 'wait',
        specificity: 1.2,
        spikes: [{
            'rawio:in:changed': 0,
            'nlp:is-question': 1,
            'visonio:is-dino': -1,
            'visonio:in:changed': -1
        }]
    },
    // Message 8: visionio:in:changed spike
    {
        type: 'spike',
        signal: 'visionio:in:changed',
        id: 2,
        parents: []
    },
    // Message 9-10: detect-objects, dinosaur-qa ref. new spike
    {
        type: 'activation',
        id: 2,
        state: 'dinosaur-qa',
        status: 'wait',
        specificity: 1.2,
        spikes: [{
            'rawio:in:changed': 0,
            'nlp:is-question': 1,
            'visonio:is-dino': -1,
            'visonio:in:changed': 2
        }]
    },
    {
        type: 'activation',
        id: 3,
        state: 'detect-objects',
        status: 'ready',
        specificity: 1.2,
        spikes: [{
            'visonio:in:changed': 2
        }]
    },
    // Message 11: detect-objects runs
    {
        type: 'activation',
        id: 3,
        state: 'detect-objects',
        status: 'run',
        specificity: 1.2,
        spikes: [{
            'visonio:in:changed': 2
        }]
    },
    // Message 12: detect-objects derefs. spikes
    {
        type: 'activation',
        id: 3,
        state: 'detect-objects',
        status: 'run',
        specificity: 1.2,
        spikes: [{
            'visonio:in:changed': -1
        }]
    },
    // Message 13-14: Follow-up spikes from visionio:in:changed
    {
        type: 'spike',
        signal: 'visionio:is-tree',
        id: 3,
        parents: [2]
    },
    {
        type: 'spike',
        signal: 'visionio:is-dino',
        id: 4,
        parents: [2]
    },
    // Message 15: dinosaur-qa refs. another spike
    {
        type: 'activation',
        id: 2,
        state: 'dinosaur-qa',
        status: 'ready',
        specificity: 1.2,
        spikes: [{
            'rawio:in:changed': 0,
            'nlp:is-question': 1,
            'visonio:is-dino': 4,
            'visonio:in:changed': 2
        }]
    },
    // Message 16-17: dinosaur-qa is run, wildtalk derefs.
    {
        type: 'activation',
        id: 0,
        state: 'wildtalk',
        specificity: 0.2,
        status: 'ready',
        spikes: [{
            'rawio:in:changed': -1
        }]
    },
    {
        type: 'activation',
        id: 2,
        state: 'dinosaur-qa',
        status: 'run',
        specificity: 1.2,
        spikes: [{
            'rawio:in:changed': 0,
            'nlp:is-question': 1,
            'visonio:is-dino': 4,
            'visonio:in:changed': 2
        }]
    },
];


@Injectable({
    providedIn: 'root'
})
export class MockDataService {

    dataStream: Subject<SpikeUpdate | ActivationUpdate>;

    activations: Observable<ActivationUpdate>;
    spikes: Observable<SpikeUpdate>;

    private randomIDCounter: number = 100;
    private mockMessageCounter: number = 0;

    private lastRandomSpikeID: number = -1;

    constructor() {
        this.dataStream = new Subject();
        this.activations = this.dataStream.pipe(filter(data => data.type === 'activation'), map(data => data as ActivationUpdate));
        this.spikes = this.dataStream.pipe(filter(data => data.type === 'spike'), map( data => data as SpikeUpdate));
   }

    public websocketTest(i) {
        console.log('start connect', i);

        const subject = webSocket("ws://localhost:5042");

        subject.subscribe(
            msg => console.log('message received: ', i, msg), // Called whenever there is a message from the server.
            err => console.log('ERROR', i, err), // Called if at any point WebSocket API signals some kind of error.
            () => console.log('complete') // Called when connection is closed (for whatever reason).
        );

    }

    public sendNextMockMessage() {
        if (this.mockMessageCounter < MOCK_MESSAGES.length) {
            this.dataStream.next(MOCK_MESSAGES[this.mockMessageCounter]);
            this.mockMessageCounter++;
        } else {
            this.sendSpike();
        }
    }

    resetMockData() {
        this.mockMessageCounter = 0;
    }

    public sendActivation() {
        this.dataStream.next({
            type: 'activation',
            id: this.randomIDCounter,
            state: 'random state',
            specificity: Math.floor(Math.random() * 100) / 100,
            status: 'ready',
            spikes: [{
                'random spike 1': this.randomIDCounter - 1,
                'random spike 2': this.randomIDCounter - 2,
                'random spike 4': this.randomIDCounter - 4,
                'another random spike': this.lastRandomSpikeID,
            }]
        });
        this.randomIDCounter++;
    }

    public sendSpike() {
        this.dataStream.next({
            type: 'spike',
            id: this.randomIDCounter,
            signal: 'random spike',
            parents: [this.randomIDCounter - 8, this.randomIDCounter - 14]
        });
        this.lastRandomSpikeID = this.randomIDCounter;
        this.randomIDCounter++;
    }

}
