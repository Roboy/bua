    var socket = io.connect('http://' + document.domain + ':' + location.port);
    var data;
    socket.on('newdata', function(newdata) {
        data = newdata
        console.log("Hello");
    });

    var nodes;
    var activeNode;

    var links = {};
    var signals = {};
    var states = {};
    var properties = {};


    $(function () {
        $.getJSON("/data", function (data) {

            links = data;

            // Expected input data format:
            //     [{source: "property_name", target: "signal_name", type: "sets"},]
            // Types of links:
            //     - changes: state -> property
            //     - triggers: signal -> state
            //     - emits: state -> signal
            //     - sets: property -> signal

            // Compute the distinct nodes from the links.
            var i = 0;
            var j = 0;
            links.forEach(function (link) {
                if (link.type === 'changes') { // state -> prop
                    link.source = states[link.source] || (states[link.source] = {name: link.source, index: i++, weight: j++});
                    link.target = properties[link.target] || (properties[link.target] = {name: link.target, index: i++, weight: j++});
                } else if (link.type === 'triggers') { // signal -> state
                    link.source = signals[link.source] || (signals[link.source] = {name: link.source, index: i++, weight: j++});
                    link.target = states[link.target] || (states[link.target] = {name: link.target, index: i++, weight: j++});
                } else if (link.type === 'emits') { // state -> signal
                    link.source = states[link.source] || (states[link.source] = {name: link.source, index: i++, weight: j++});
                    link.target = signals[link.target] || (signals[link.target] = {name: link.target, index: i++, weight: j++});
                } else if (link.type === 'sets') { // prop -> signal
                    link.source = properties[link.source] || (properties[link.source] = {name: link.source, index: i++, weight: j++});
                    link.target = signals[link.target] || (signals[link.target] = {name: link.target, index: i++, weight: j++});
                } else {
                    console.log(link);
                }
            });



            nodes = Object.assign({}, signals, states, properties);
            console.log(nodes)

            var width = window.innerWidth,
                height = window.innerHeight;

            var simulation = d3.forceSimulation(d3.values(nodes))
                .force('collision', d3.forceCollide().radius( function(d) {return (d.name in states) ? 70 : 50}))
                .force('charge', d3.forceManyBody().strength(1))
                .force('center', d3.forceCenter(width/2, height/2))
                .force('link', d3.forceLink().links(links).distance(height/6))
                .on("tick", tick);

            // ---------- Setup graph wrapper ------------
            var svg = d3.select("#chart")
                .classed("svg-container", true)
                .append("svg")
                .attr("preserveAspectRatio", "xMinYMin meet")
                .attr("viewBox", "0 0 " + width + " " + height)
                .classed("svg-content-responsive", true);

            // Per-type markers, as they don't inherit styles.
            svg.append("defs").selectAll("marker")
                .data(["triggers"])
                .enter().append("marker")
                .attr("id", function (d) {
                    return d;
                })
                .attr("viewBox", "0 -5 10 10")
                .attr("refX", 42) // Increase with larger circle radius
                .attr("refY", -4)  // Decrease with increasing radius to counter arc
                .attr("markerWidth", 10)
                .attr("markerHeight", 10)
                .attr("orient", "auto")
                .attr("fill", "#ffffff")
                .append("path")
                .attr("d", "M0,-5L10,0L0,5");

            var path = svg.append("g").selectAll("path")
                .data(links)
                .enter().append("path")
                .attr("class", function (d) {
                    return "link " + d.type;
                })
                .attr("marker-end", function (d) {
                    return "url(#" + d.type + ")";
                });

            var circle = svg.append("g").selectAll("circle")
                .data(d3.values(nodes))
                .enter().append("circle")
                .attr("r", function (d) {
                    return (d.name in states) ? 50 : 30})
                .attr("radius", function (d) {
                    return (d.name in states) ? 50 : 30})
                .attr("class", function (d) {
                    return (d.name in signals) ? "signal" :
                        ((d.name in states) ? "state" : "prop")})
                .attr("nodeName", function (d) {
                    return d.name
                })
                .call(d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));

        function dragstarted(d)
         {
            simulation.restart();
            simulation.alpha(1.0);
            d.fx = d.x;
            d.fy = d.y;
         }

         function dragged(d)
         {
            d.fx = d3.event.x;
            d.fy = d3.event.y;
         }

         function dragended(d)
         {
            d.fx = null;
            d.fy = null;
            simulation.alphaTarget(0.1);
            d["staticnode"] = "true";
            d["staticx"] = d.x;
            d["staticy"] = d.y;

         }

            var text = svg.append("g").selectAll("text")
                .data(d3.values(nodes))
                .enter().append("text")
                .attr("x", -43)
                .attr("y", 0)
                .text(function (d) {
                    return d.name;
                });

            // Use elliptical arc path segments to doubly-encode directionality.
            function tick() {
                circle.attr("transform", transform);
                text.attr("transform", transform);
                path.attr("d", linkArc);
            }

            function linkArc(d) {
                var dx = d.target.x - d.source.x,
                    dy = d.target.y - d.source.y,
                    dr = Math.sqrt(dx * dx + dy * dy);
                return "M" + d.source.x + "," + d.source.y + "A" + dr + "," + dr + " 0 0,1 " + d.target.x + "," + d.target.y;
            }

            function transform(d) {
                if(!d["staticnode"]) {
                    return "translate(" + d.x + "," + d.y + ")";
                    }
                else {
                    d.x = d["staticx"];
                    d.y = d["staticy"];
                    return "translate(" + d["staticx"] + "," + d["staticy"] + ")";
                }
            }

            socket.on('activate', function(stateName){
                $("circle").one('animationiteration webkitAnimationIteration', function() {
                     $(this).removeClass("democolor");
                });
                if(activeNode) {
                    activeNode.attr("activated", "off");
                }
                var activaaate =d3.select("[nodeName=\"" + stateName + "\"]");
                activaaate.attr("democolor", "on");
                activaaate.attr("activated", "on");
                activeNode = activaaate;
            });


            socket.on('spike', function(stateName){
                $("circle").one('animationiteration webkitAnimationIteration', function() {
                     $(this).removeClass("spiking");
                });
                d3.select("[nodeName=\"" + stateName + "\"]").attr("spiking", "on");
            });

        });

    })
