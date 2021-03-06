import { Component, Input } from '@angular/core';

@Component({
    selector: '[connector]',
    template: `
        <svg:path class="connector-line" [attr.d]="pathD"/>
    `,
    styleUrls: ['./styles.scss']
})
export class ConnectorComponent {

    @Input() fromX: number = 0;
    @Input() fromY: number = 0;

    @Input() toX: number = 0;
    @Input() toY: number = 0;

    get pathD(): string {
        // bezier control points
        const c1 = {
            x: Math.round((this.fromX + this.toX * 2) / 3),
            y: Math.round((this.fromY * 3 + this.toY) / 4),
        };
        const c2 = {
            x: Math.round((this.fromX * 2 + this.toX) / 3),
            y: Math.round((this.fromY + this.toY * 3) / 4),
        };
        return `M ${this.fromX} ${this.fromY} C ${c1.x} ${c1.y} ${c2.x} ${c2.y} ${this.toX} ${this.toY}`;
    }
}
