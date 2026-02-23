"""
Process Capability (Cp/Cpk) Calculations Service
==================================================
Calculates Cp, Cpk, Cpm, Pp, Ppk capability indices.
"""
import math
from typing import Dict, Any, List, Optional


class SPCCapabilityService:
    def __init__(self, session=None):
        self.session = session

    def calculate_capability(self, data: List[float], usl: float, lsl: float,
                             target: float = None) -> Dict[str, Any]:
        """Calculate process capability indices."""
        if len(data) < 2:
            return {'error': 'Need at least 2 data points'}
        if usl <= lsl:
            return {'error': 'USL must be greater than LSL'}

        n = len(data)
        mean = sum(data) / n
        variance = sum((x - mean) ** 2 for x in data) / (n - 1)
        sigma = math.sqrt(variance) if variance > 0 else 0.0001
        target = target if target is not None else (usl + lsl) / 2

        # Cp - Process Capability
        cp = (usl - lsl) / (6 * sigma)

        # Cpk - Process Capability Index (accounts for centering)
        cpu = (usl - mean) / (3 * sigma)
        cpl = (mean - lsl) / (3 * sigma)
        cpk = min(cpu, cpl)

        # Cpm - Taguchi capability (accounts for target)
        tau = math.sqrt(variance + (mean - target) ** 2)
        cpm = (usl - lsl) / (6 * tau) if tau > 0 else 0

        # Pp, Ppk - Performance indices (using overall sigma)
        pp = cp  # Same as Cp for single sample
        ppk = cpk

        # Determine status
        if cpk >= 1.33:
            status = 'capable'
            color = 'green'
        elif cpk >= 1.0:
            status = 'marginally_capable'
            color = 'yellow'
        else:
            status = 'not_capable'
            color = 'red'

        # Estimated defect rate (PPM)
        z_score = min(cpu, cpl) * 3
        ppm = self._z_to_ppm(z_score)

        return {
            'n': n, 'mean': round(mean, 4), 'sigma': round(sigma, 4),
            'usl': usl, 'lsl': lsl, 'target': target,
            'cp': round(cp, 3), 'cpk': round(cpk, 3),
            'cpu': round(cpu, 3), 'cpl': round(cpl, 3),
            'cpm': round(cpm, 3),
            'pp': round(pp, 3), 'ppk': round(ppk, 3),
            'estimated_ppm': round(ppm, 1),
            'status': status, 'color': color,
        }

    def _z_to_ppm(self, z: float) -> float:
        """Approximate PPM from Z-score."""
        if z >= 6:
            return 0.001
        if z <= 0:
            return 500000
        # Approximation using error function
        t = 1 / (1 + 0.2316419 * abs(z))
        d = 0.3989423 * math.exp(-z * z / 2)
        p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
        return p * 1000000

    def get_capability_summary(self, charts_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get capability summary for multiple SPC charts."""
        results = []
        for chart in charts_data:
            data = chart.get('readings', [])
            usl = chart.get('usl')
            lsl = chart.get('lsl')
            if data and usl is not None and lsl is not None:
                cap = self.calculate_capability(data, usl, lsl)
                cap['chart_name'] = chart.get('name', 'Unknown')
                cap['chart_id'] = chart.get('id')
                results.append(cap)
        return sorted(results, key=lambda x: x.get('cpk', 0))
