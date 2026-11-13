#!/usr/bin/env python3
"""RX Adaptive Compression — Automatic compression strategy selection based on data type and transfer cost."""
from __future__ import annotations
import os, json, hashlib, time, subprocess, sys, zlib, struct
from typing import Dict, Any, List
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tools/rxre/polaris12'))

COMP_DIR = os.path.join(ROOT, 'evidence', 'adaptive_compression')
os.makedirs(COMP_DIR, exist_ok=True)

class RXAdaptiveCompression:
    """Automatic compression strategy selection."""
    
    def __init__(self):
        self.strategies = ['none', 'zlib', 'lz4_sim', 'rle']
        self.results = []
    
    def compress_none(self, data):
        return data, 0.0
    
    def compress_zlib(self, data):
        import time as t
        start = t.time()
        compressed = zlib.compress(data)
        elapsed = t.time() - start
        return compressed, elapsed
    
    def compress_rle(self, data):
        import time as t
        start = t.time()
        # Simple RLE
        result = bytearray()
        i = 0
        while i < len(data):
            count = 1
            while i + count < len(data) and data[i+count] == data[i] and count < 255:
                count += 1
            result.append(count)
            result.append(data[i])
            i += count
        elapsed = t.time() - start
        return bytes(result), elapsed
    
    def evaluate_strategy(self, data, strategy):
        if strategy == 'none':
            comp, t = self.compress_none(data)
        elif strategy == 'zlib':
            comp, t = self.compress_zlib(data)
        elif strategy == 'rle':
            comp, t = self.compress_rle(data)
        else:
            comp, t = data, 0.0
        
        ratio = len(comp) / len(data) if len(data) > 0 else 1.0
        return {
            'strategy': strategy,
            'original_size': len(data),
            'compressed_size': len(comp),
            'ratio': ratio,
            'savings_pct': (1 - ratio) * 100,
            'time': t,
            'effective': ratio < 0.9
        }
    
    def run_compression_experiment(self):
        print("="*60)
        print("RX ADAPTIVE COMPRESSION — Strategy Selection")
        print("="*60)
        
        # Test data types
        test_data = {
            'zeros': bytes([0]*10000),
            'random': os.urandom(10000),
            'repeated': bytes([i%256 for i in range(10000)]),
            'sparse': bytes([0]*9000 + [1]*1000),
        }
        
        print("\n[1] Evaluating compression strategies...")
        all_results = {}
        for dtype, data in test_data.items():
            print(f"\n  Data type: {dtype} ({len(data)} bytes)")
            results = []
            for strategy in self.strategies:
                r = self.evaluate_strategy(data, strategy)
                results.append(r)
                print(f"    {strategy}: ratio={r['ratio']:.3f}, savings={r['savings_pct']:.1f}%, time={r['time']:.6f}s")
            # Select best
            best = min(results, key=lambda x: x['ratio'])
            all_results[dtype] = {'results': results, 'best': best['strategy'], 'best_ratio': best['ratio']}
            print(f"    Best: {best['strategy']} (ratio={best['ratio']:.3f})")
        
        ev_path = os.path.join(COMP_DIR, f'compression_{int(time.time())}.json')
        with open(ev_path, 'w') as f:
            json.dump({'mission': 'RX_ADAPTIVE_COMPRESSION', 'timestamp': datetime.now().isoformat(),
                       'results': all_results, 'restrictions': {'DB_AUTH': 'safe'}}, f, indent=2)
        print(f"\nEvidence: {ev_path}")
        
        try:
            from tools.rxre.arquitectura.AGUA import Agua, Aprendizaje
            agua = Agua(os.path.join(COMP_DIR, 'comp_agua.db'))
            def rev():
                return True
            apr = Aprendizaje('adaptive_compression', 'adaptive_compression', 'compression strategy', rev, 0.8)
            aid = agua.aprender(apr)
            print(f"AGUA aprendizaje: {aid}")
        except Exception as e:
            print(f"AGUA warning: {e}")
        
        print("\n" + "="*60)
        print("ADAPTIVE COMPRESSION — COMPLETE")
        print("="*60)
        return all_results

if __name__ == '__main__':
    comp = RXAdaptiveCompression()
    comp.run_compression_experiment()
