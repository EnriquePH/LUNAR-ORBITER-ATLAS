// Keep the globe controllable up close.
//
// Plotly turns a drag into a fixed angle per pixel and a wheel step into a
// fixed share of the camera's distance from the centre, so near the surface
// the Moon races under the cursor and the zoom overshoots. Before Plotly
// handles a press or a wheel turn on the globe, this scales both speeds by the
// camera's height above the surface (full speed at the starting view). It
// also lets the camera come down to just above the photos, pulling the near
// clipping plane in so the surface is not cut away.
(function () {
    // Eye distance of the starting view (CAMERA_DISTANCE in orbiter/globe.py).
    const FULL_SPEED_DISTANCE = 1.6;
    const MIN_SPEED = 0.002;
    // Closest and farthest camera, in Moon radii from the centre. Photos float
    // up to 1.006 radii and their labels at 1.008 (orbiter/globe.py).
    const MIN_DISTANCE_RADII = 1.01;
    const MAX_DISTANCE_RADII = 12;
    // Plotly's default near plane (0.01) would cut the ground below a close camera.
    const Z_NEAR = 0.0005;
    const Z_FAR = 50;

    function globeScene(element) {
        const plot = element && element.closest && element.closest("#globe .js-plotly-plot");
        const scene = plot && plot._fullLayout && plot._fullLayout.scene
            && plot._fullLayout.scene._scene;
        return scene && scene.camera && scene.fullSceneLayout && scene.glplot ? scene : null;
    }

    function clamp(value) {
        return Math.min(1, Math.max(MIN_SPEED, value));
    }

    function tune(scene) {
        const glplot = scene.glplot;
        if (glplot.zNear !== Z_NEAR) {
            glplot.zNear = Z_NEAR;
            glplot.zFar = Z_FAR;
            if (glplot.redraw) {
                glplot.redraw();
            }
        }
        // Eye units put the scene box (aspectratio) around the axis range, so
        // the Moon (radius 1 in data units) measures aspectratio / range span.
        const layout = scene.fullSceneLayout;
        const range = layout.xaxis.range;
        const radius = layout.aspectratio.x / (range[1] - range[0]);
        scene.camera.view.setDistanceLimits(
            radius * MIN_DISTANCE_RADII, radius * MAX_DISTANCE_RADII
        );
        const distance = scene.camera.distance;
        const height = (distance - radius) / (FULL_SPEED_DISTANCE - radius);
        scene.camera.rotateSpeed = clamp(height);
        // A wheel step moves the camera by a share of its distance; keep it a
        // share of the height instead.
        const start = (FULL_SPEED_DISTANCE - radius) / FULL_SPEED_DISTANCE;
        scene.camera.zoomSpeed = clamp((distance - radius) / distance / start);
    }

    function onInput(event) {
        const scene = globeScene(event.target);
        if (scene) {
            tune(scene);
        }
    }

    // Capture phase: runs before Plotly handles the same event.
    const options = { capture: true, passive: true };
    document.addEventListener("mousedown", onInput, options);
    document.addEventListener("touchstart", onInput, options);
    document.addEventListener("wheel", onInput, options);
    // A redrawn or remounted globe (new mission, tab switch) gets a fresh scene.
    setInterval(function () {
        const scene = globeScene(document.querySelector("#globe .js-plotly-plot"));
        if (scene) {
            tune(scene);
        }
    }, 500);
})();
