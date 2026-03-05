"""
QuantumFold-Pro: Production-grade quantum-enhanced protein folding.

A realistic hybrid quantum-classical system that uses:
- Classical MD for full protein (AMBER-style force fields)
- Quantum VQE for critical small fragments
- Adaptive hybrid optimization

Example:
    >>> from quantumfold import QuantumFoldPro
    >>> qfp = QuantumFoldPro()
    >>> result = qfp.fold("AEAAAKEAAA")
    >>> result.save_pdb("output.pdb")
"""

__version__ = "0.1.0"
__author__ = "Tommaso R. Marena"
__email__ = "tmarena@cua.edu"

from .force_fields import AMBERForceField, ForceFieldParams
from .quantum_engine import QuantumElectronicStructure, QuantumConfig
from .hybrid_optimizer import QuantumClassicalHybrid, HybridConfig
from .structure_utils import (
    ProteinStructure, 
    save_pdb, 
    load_pdb,
    compute_rmsd,
    compute_tm_score,
    generate_extended_chain,
    generate_helix
)

import numpy as np
from typing import Optional
from dataclasses import dataclass


@dataclass
class FoldingResult:
    """Container for folding results."""
    sequence: str
    coordinates: np.ndarray
    energy: float
    trajectory: dict
    quantum_energy_fraction: float
    rmsd_from_initial: float
    
    def save_pdb(self, filename: str, confidence_scores: Optional[np.ndarray] = None):
        """Save structure to PDB file."""
        structure = ProteinStructure(
            sequence=self.sequence,
            coordinates=self.coordinates
        )
        save_pdb(structure, filename, confidence_scores)


class QuantumFoldPro:
    """
    Main interface for quantum-enhanced protein folding.
    
    This class coordinates:
    1. Classical force field (AMBER-style)
    2. Quantum electronic structure (VQE)
    3. Hybrid optimization (MD + quantum refinement)
    
    Attributes:
        force_field: Classical molecular mechanics
        quantum_engine: Variational quantum eigensolver
        hybrid_optimizer: Quantum-classical coordinator
    """
    
    def __init__(
        self,
        force_field_params: Optional[ForceFieldParams] = None,
        quantum_config: Optional[QuantumConfig] = None,
        hybrid_config: Optional[HybridConfig] = None,
        verbose: bool = False
    ):
        """
        Initialize QuantumFold-Pro system.
        
        Args:
            force_field_params: Classical force field configuration
            quantum_config: Quantum engine configuration
            hybrid_config: Hybrid optimizer configuration
            verbose: Print initialization info
        """
        self.verbose = verbose
        
        # Initialize components
        self.force_field = AMBERForceField(force_field_params)
        self.quantum_engine = QuantumElectronicStructure(quantum_config)
        self.hybrid_optimizer = QuantumClassicalHybrid(
            self.force_field,
            self.quantum_engine,
            hybrid_config
        )
        
        if verbose:
            print("QuantumFold-Pro initialized")
            print(f"  Force field: AMBER-style with proper physics")
            print(f"  Quantum engine: VQE with {self.quantum_engine.config.n_qubits} qubits")
            print(f"  Optimizer: Hybrid MD + quantum refinement")
    
    def fold(
        self,
        sequence: str,
        initial_coords: Optional[np.ndarray] = None,
        active_site_residues: Optional[list] = None,
        verbose: Optional[bool] = None
    ) -> FoldingResult:
        """
        Fold a protein sequence to 3D structure.
        
        Args:
            sequence: Amino acid sequence (single-letter codes)
            initial_coords: Optional starting coordinates (default: extended chain)
            active_site_residues: Optional list of residue indices for quantum treatment
            verbose: Override default verbosity
            
        Returns:
            FoldingResult with structure, energy, and metadata
        """
        verbose = verbose if verbose is not None else self.verbose
        
        # Validate sequence
        valid_aas = set('ACDEFGHIKLMNPQRSTVWY')
        if not all(aa in valid_aas for aa in sequence):
            raise ValueError(f"Invalid amino acids in sequence")
        
        if len(sequence) < 5:
            raise ValueError("Sequence too short (minimum 5 residues)")
        
        if len(sequence) > 500:
            print("Warning: Long sequences (>500 residues) may be slow")
        
        # Initialize coordinates
        if initial_coords is None:
            initial_coords = generate_extended_chain(sequence)
        
        if initial_coords.shape != (len(sequence), 3):
            raise ValueError(f"Coordinate shape mismatch: {initial_coords.shape} vs ({len(sequence)}, 3)")
        
        # Set active site if specified
        if active_site_residues:
            self.hybrid_optimizer.config.active_site_residues = active_site_residues
        
        # Run optimization
        if verbose:
            print(f"\nFolding sequence: {sequence[:20]}{'...' if len(sequence) > 20 else ''}")
            print(f"Length: {len(sequence)} residues")
        
        optimized_coords, trajectory = self.hybrid_optimizer.optimize_structure(
            initial_coords,
            sequence,
            verbose=verbose
        )
        
        # Compute final metrics
        final_energy = trajectory['total_energy'][-1]
        quantum_contribution = np.mean([abs(qe) for qe in trajectory['quantum_energy'] if qe != 0])
        total_contribution = abs(final_energy) if final_energy != 0 else 1
        quantum_fraction = quantum_contribution / total_contribution if total_contribution > 0 else 0
        
        rmsd = compute_rmsd(initial_coords, optimized_coords, align=True)
        
        return FoldingResult(
            sequence=sequence,
            coordinates=optimized_coords,
            energy=final_energy,
            trajectory=trajectory,
            quantum_energy_fraction=quantum_fraction,
            rmsd_from_initial=rmsd
        )
    
    def benchmark(self, pdb_file: str, verbose: bool = True) -> dict:
        """
        Benchmark against known PDB structure.
        
        Args:
            pdb_file: Path to PDB file with known structure
            verbose: Print results
            
        Returns:
            Dictionary with RMSD, TM-score, and energy metrics
        """
        # Load reference structure
        ref_structure = load_pdb(pdb_file)
        
        # Fold from sequence
        result = self.fold(ref_structure.sequence, verbose=verbose)
        
        # Compute metrics
        rmsd = compute_rmsd(ref_structure.coordinates, result.coordinates)
        tm_score = compute_tm_score(ref_structure.coordinates, result.coordinates)
        
        metrics = {
            'rmsd': rmsd,
            'tm_score': tm_score,
            'energy': result.energy,
            'quantum_fraction': result.quantum_energy_fraction,
            'sequence_length': len(ref_structure.sequence)
        }
        
        if verbose:
            print(f"\nBenchmark Results:")
            print(f"  RMSD: {rmsd:.2f} Å")
            print(f"  TM-score: {tm_score:.4f}")
            print(f"  Final energy: {result.energy:.2f} kcal/mol")
        
        return metrics


__all__ = [
    'QuantumFoldPro',
    'FoldingResult',
    'AMBERForceField',
    'ForceFieldParams',
    'QuantumElectronicStructure',
    'QuantumConfig',
    'QuantumClassicalHybrid',
    'HybridConfig',
    'ProteinStructure',
    'save_pdb',
    'load_pdb',
    'compute_rmsd',
    'compute_tm_score',
]
