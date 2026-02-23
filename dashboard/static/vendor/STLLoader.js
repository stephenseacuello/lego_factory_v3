/**
 * Three.js STL Loader Placeholder
 * 
 * This file should be replaced with the actual STLLoader.
 * 
 * Get it from Three.js examples:
 * https://github.com/mrdoob/three.js/blob/master/examples/js/loaders/STLLoader.js
 * 
 * Or use CDN version
 */

if (typeof THREE !== 'undefined' && typeof THREE.STLLoader === 'undefined') {
    console.warn('STLLoader not loaded. STL preview will not work.');
    
    THREE.STLLoader = function() {};
    THREE.STLLoader.prototype.load = function(url, callback) {
        console.warn('STLLoader: Cannot load', url);
    };
}
