// Keep the globe controllable up close.
//
// Plotly turns a drag into a fixed angle per pixel, so near the surface the
// Moon races under the cursor and a photo is hard to reach; its wheel zoom
// also flies straight through the Moon. Before Plotly handles a press or a
// wheel turn on the globe, this scales the rotation speed by the camera's
// height above the surface (full speed at the starting view) and stops the
// zoom just above the surface.
(function () {
    // Eye distance of the starting view (CAMERA_DISTANCE in orbiter/globe.py).
    const FULL_SPEED_DISTANCE = 1.6;
    const MIN_SPEED = 0.02;
    // Closest and farthest camera, in Moon radii from the centre.
    const MIN_DISTANCE_RADII = 1.08;
    const MAX_DISTANCE_RADII = 12;

    function adjustCamera(event) {
        const plot = event.target.closest && event.target.closest("#globe .js-plotly-plot");
        const scene = plot && plot._fullLayout && plot._fullLayout.scene
            && plot._fullLayout.scene._scene;
        if (!scene || !scene.camera || !scene.dataScale) {
            return;
        }
        // The Moon has radius 1 in data units; dataScale maps it to eye units.
        const radius = Math.max(...scene.dataScale);
        scene.camera.view.setDistanceLimits(
            radius * MIN_DISTANCE_RADII, radius * MAX_DISTANCE_RADII
        );
        const distance = scene.camera.distance;
        const speed = (distance - radius) / (FULL_SPEED_DISTANCE - radius);
        scene.camera.rotateSpeed = Math.min(1, Math.max(MIN_SPEED, speed));
    }

    // Capture phase: runs before Plotly handles the same event.
    const options = { capture: true, passive: true };
    document.addEventListener("mousedown", adjustCamera, options);
    document.addEventListener("touchstart", adjustCamera, options);
    document.addEventListener("wheel", adjustCamera, options);
})();
