#!/usr/bin/env python3
"""
Simple test script for requirement extraction + job submission API.

Usage:
    python scripts/test_extract_and_submit.py
"""

import asyncio
import aiohttp

# BASE_URL = "https://tool-generation-service.up.railway.app"
BASE_URL = "http://localhost:8000"

# task_descriptions = [
#     r"""
#     **1.Organic Compounds, Level 1**
#     For the three compounds listed below, perform a geometry optimization using the Hartree-Fock (HF) method and the def2-SVP basis set in the gas phase.
#     After optimization, generate a separate report for each molecule. Each report must contain:
#     Final Cartesian coordinates (in Å)
#     Total energy (in Hartrees)
#     Point group symmetry
#     Dipole moment (in Debye)
#     Molecular orbital analysis (including an MO energy table and the HOMO–LUMO gap)
#     Atomic charge analysis (Mulliken, Löwdin, and Hirshfeld)
#     Compounds:
#     caffeine: CN1C=NC2=C1C(=O)N(C(=O)N2C)C
#     theobromine: CN1C=NC2=C1C(=O)NC(=O)N2C
#     acetylsalicylic_acid: CC(=O)OC1=CC=CC=C1C(=O)O
#     """,
#     r"""
#     **2.Inorganic Compounds, Level 1**
#     For the 20 molecules defined below by their filenames, charge, and multiplicity, perform a geometry optimization with the Hartree-Fock (HF) method and the def2-SVP basis set in the gas phase. Assume you have access to the initial geometry from the corresponding XYZ files.
#     After optimization, generate a separate report for each molecule. Each report must contain the same 7 points as in the Level 1 query (Final Coordinates, Total Energy, Point Group, Dipole Moment, MO Analysis, Atomic Charge Analysis, and an image).
#     Molecules:
#     caffeine_openbabel.xyz (charge = 0; multiplicity = 1)
#     theobromine_openbabel.xyz (charge = 0; multiplicity = 1)
#     aspirin_openbabel.xyz (charge = 0; multiplicity = 1)
#     methyl_salicylate_openbabel.xyz (charge = 0; multiplicity = 1)
#     acetaminophen_openbabel.xyz (charge = 0; multiplicity = 1)
#     triazaadamantane_openbabel.xyz (charge = 0; multiplicity = 1)
#     limonene_openbabel.xyz (charge = 0; multiplicity = 1)
#     D-glucose_pubchem.xyz (charge = 0; multiplicity = 1)
#     creatinine_amine_tautomer_openbabel.xyz (charge = 0; multiplicity = 1)
#     creatinine_imine_tautomer_openbabel.xyz (charge = 0; multiplicity = 1)
#     L-phenylalanine_zwitterion_openbabel.xyz (charge = 0; multiplicity = 1)
#     2-chloronitrobenzene_openbabel.xyz (charge = 0; multiplicity = 1)
#     cis-1_2-cyclohexanediol_openbabel.xyz (charge = 0; multiplicity = 1)
#     L-histidine_non_zwitterion_openbabel.xyz (charge = 0; multiplicity = 1)
#     2_2-biphenol_openbabel.xyz (charge = 0; multiplicity = 1)
#     S-2-ethyl-2-fluoropentan-1-ol_openbabel.xyz (charge = 0; multiplicity = 1)
#     R-3-hydroxycyclopentan-1-one_openbabel.xyz (charge = 0; multiplicity = 1)
#     3-methylbutanoate_anion_openbabel.xyz (charge = -1; multiplicity = 1)
#     diisopropylamide_anion_openbabel.xyz (charge = -1; multiplicity = 1)
#     diisopropylammonium_cation_openbabel.xyz (charge = +1; multiplicity = 1)
#     """,
#     r"""
#     **3.Relative Stability of Carbocations, Level 1**
#     Calculate the carbocation formation enthalpies (ΔH) and Gibbs free energies (ΔG) for the reaction:
#     R-H -> R+ + H-
#     The R-H compounds to study are: methane, ethane, propane, 2-methylpropane, toluene, benzene, dimethyl ether, trimethylamine, and propene.
#     You are provided with initial XYZ geometry files for all R-H (molecules), R+ (carbocations), and H- (hydride) species.
#     Instructions:
#     Optimize the structures of all R-H and R+ species using DFT with the B3LYP functional and 6-31G* basis set. The provided hydride (H-) structure should be used as-is without optimization.
#     Use the following charge and multiplicity:
#     R-H molecules: charge 0, multiplicity 1
#     R+ carbocations: charge 1, multiplicity 1
#     Hydride (H-): charge -1, multiplicity 1
#     From the outputs, calculate the formation enthalpy and Gibbs free energy for each R-H compound's reaction.
#     Report the results (in kcal/mol) in a table and save it to a text file.
#     """,
#     r"""
#     **4.Ring Strain Energies, Level 1**
#     Your goal is to compute the relative ring strain energies (RSE) for cycloalkanes from C3 to C8.
#     Calculate Reaction Energies: Compute the ΔH and ΔG for the following reactions, for n = 4, 5, 6, 7, and 8:
#     cyclo(Cn​H2n​)→cyclo(Cn−1​H2n−3​)-CH3​
#     Use the B3LYP/6-31G(d) level of theory.
#     All structures must be optimized, and frequency calculations are required to obtain enthalpies and Gibbs free energies.
#     The first reaction ($n=4$) is cyclobutane (C1CCC1) $\rightarrow$ methylcyclopropane (CC1CC1). You must generate the other reactants and products.
#     Calculate Relative RSE:
#     First, determine RSE values by setting the RSE of cyclooctane ($n=8$) to zero.
#     The RSE of $\text{cyclo}(C_{n-1}H_{2n-2})$ is the RSE of $\text{cyclo}(C_nH_{2n})$ plus the reaction energy ($\Delta H$ or $\Delta G$) calculated in step 1.
#     Calculate this iteratively down to $n=3$.
#     Report Final Table:
#     Renormalize the RSE values, setting the RSE of cyclohexane ($n=6$) as the zero reference point.
#     Report the final results as a table of ring size (n=3 to 8) vs. RSE ($\Delta H$ and $\Delta G$).
#     """,
#     r"""
#     **5.pKa of Common Acids, Level 1**
#     Calculate the pKa of acetic acid in water using a thermodynamic cycle. Perform the necessary geometry optimization and frequency calculations for the acid and its conjugate base at the B3LYP/6-31G* level of theory with the CPCM implicit solvation model (water). You must use an appropriate value for the solvation free energy of the proton to complete the calculation.
#     """,
#     r"""
#     **6.Absorption Spectrum of Organic Molecules, Level 1**
#     For the three molecules provided as 2.xyz, 3.xyz, and 5.xyz, compute the following properties:
#     Energy of the first singlet excited state (S1)
#     Energy difference between S1 and the first triplet excited state (T1)
#     Oscillator strength to the S1 state
#     Method:
#     Perform a single-point TDDFT calculation.
#     Use a double-hybrid functional comparable to wB2PLYP with a medium split-valence basis set (e.g., def2-mSVP or equivalent).
#     Apply RI or similar integral approximations if available.
#     Include both singlet and triplet states (ensure sufficient nroots and triplets)
#     Report the oscillator strength corresponding to the S1 transition.
#     """,
#     r"""
#     **7. Case Study: Influence of Solvent on IR Spectra**
#     Investigate the effect of solvent (water) on the vibrational frequencies of an alanine molecule by comparing its IR spectrum under three distinct conditions:
#     Gas Phase: Alanine optimized in a vacuum.
#     Implicit Solvent: Alanine optimized with the CPCM implicit solvation model for water.
#     Explicit + Implicit Solvent: A complex of (Alanine + 12 H2O molecules) optimized with the CPCM implicit solvation model for water.
#     Use the PBE0/def2-TZVP level of theory for geometry optimization and frequency analysis for all three systems.
#     Generate a final report comparing the three IR spectra, highlighting any significant frequency shifts for key vibrational modes.
#     """,
#     r"""
#     **8. Case Study: Lanthanoid Complex**
#     Perform a two-step calculation (geometry optimization followed by a single-point energy calculation) for a lanthanide complex.
#     Complex Definition:
#     Metal core: Cerium (Ce)
#     Oxidation state: +3
#     Total charge: 0
#     Multiplicity: 2
#     Ligands: Three bidentate nitrate ligands and three water molecules
#
#
#     Conformational Requirement:
#      Multiple conformers may exist. All distinct conformers must be identified, optimized, and evaluated using the same computational protocol. Report the final electronic energy for each conformer found.
#     Step 1: Geometry Optimization
#     Exchange–correlation functional: PBE0
#     Basis set: def2-SVP (or an equivalently sized all-electron basis set)
#     Dispersion correction: Include a modern atom-pairwise correction (e.g., D4 or equivalent).
#     Numerical integration grid: Medium–fine accuracy (comparable to a “DEFGRID2” setting).
#     Convergence criteria: Tight optimization and self-consistent field (SCF) convergence; allow at least 500 SCF iterations if needed.
#     Relativistic treatment: Use a small-core effective core potential (ECP) for Ce or an equivalent scalar-relativistic treatment.
#     Step 2: Single-Point Energy Calculation
#     Exchange–correlation functional: ωB97M-V
#     Basis set: def2-SVPD (or an equivalently extended diffuse basis).
#     Other settings: Use the same relativistic and dispersion treatments as in Step 1.
#
#
#     Reporting:
#     For each conformer:
#     Provide the optimized structure.
#     Report the total electronic energy from the single-point calculation.
#     List relative energies between conformers.
#     """
# ]

task_descriptions = [
"""
**1. Organic Compounds, Level 2**
For the 20 molecules defined below by their filenames, charge, and multiplicity, perform a geometry optimization with the Hartree-Fock (HF) method and the def2-SVP basis set in the gas phase. Assume you have access to the initial geometry from the corresponding XYZ files.
After optimization, generate a separate report for each molecule. Each report must contain the same 7 points as in the Level 1 query (Final Coordinates, Total Energy, Point Group, Dipole Moment, MO Analysis, Atomic Charge Analysis, and an image).
Molecules:
caffeine_openbabel.xyz (charge = 0; multiplicity = 1)
theobromine_openbabel.xyz (charge = 0; multiplicity = 1)
aspirin_openbabel.xyz (charge = 0; multiplicity = 1)
methyl_salicylate_openbabel.xyz (charge = 0; multiplicity = 1)
acetaminophen_openbabel.xyz (charge = 0; multiplicity = 1)
triazaadamantane_openbabel.xyz (charge = 0; multiplicity = 1)
limonene_openbabel.xyz (charge = 0; multiplicity = 1)
D-glucose_pubchem.xyz (charge = 0; multiplicity = 1)
creatinine_amine_tautomer_openbabel.xyz (charge = 0; multiplicity = 1)
creatinine_imine_tautomer_openbabel.xyz (charge = 0; multiplicity = 1)
L-phenylalanine_zwitterion_openbabel.xyz (charge = 0; multiplicity = 1)
2-chloronitrobenzene_openbabel.xyz (charge = 0; multiplicity = 1)
cis-1_2-cyclohexanediol_openbabel.xyz (charge = 0; multiplicity = 1)
L-histidine_non_zwitterion_openbabel.xyz (charge = 0; multiplicity = 1)
2_2-biphenol_openbabel.xyz (charge = 0; multiplicity = 1)
S-2-ethyl-2-fluoropentan-1-ol_openbabel.xyz (charge = 0; multiplicity = 1)
R-3-hydroxycyclopentan-1-one_openbabel.xyz (charge = 0; multiplicity = 1)
3-methylbutanoate_anion_openbabel.xyz (charge = -1; multiplicity = 1)
diisopropylamide_anion_openbabel.xyz (charge = -1; multiplicity = 1)
diisopropylammonium_cation_openbabel.xyz (charge = +1; multiplicity = 1)

"""
]

async def test_extract_and_submit(task_description: str):
    """Test the extract and submit endpoint."""

    # Task description to extract requirements from

    print("🚀 Testing Requirement Extraction + Job Submission")
    print("=" * 60)
    print(f"\n📝 Task Description:")
    print(f"   {task_description.strip()}")

    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Submit to extract-and-submit endpoint
            print(f"\n1️⃣ Calling /api/v1/extract-and-submit...")

            request_payload = {
                "task_description": task_description,
                "client_id": "test-extract-script"
            }

            async with session.post(
                f"{BASE_URL}/api/v1/extract-and-submit",
                json=request_payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    extract_response = await response.json()

                    print(f"   ✅ Requirements extracted and job submitted!")
                    print(f"   Job ID: {extract_response['job_id']}")
                    print(f"   Requirements extracted: {extract_response['requirements_count']}")
                    print(f"   Status: {extract_response['status']}")

                    job_id = extract_response['job_id']
                else:
                    error_text = await response.text()
                    print(f"   ❌ Failed: {response.status}")
                    print(f"   Error: {error_text}")
                    return

            # Step 2: Monitor job status
            print(f"\n2️⃣ Monitoring job {job_id}...")
            max_attempts = 30  # 10 minutes
            attempt = 0

            while attempt < max_attempts:
                attempt += 1

                async with session.get(f"{BASE_URL}/api/v1/jobs/{job_id}") as response:
                    if response.status == 200:
                        status_data = await response.json()
                        status = status_data["status"]
                        progress = status_data.get("progress", {})

                        print(f"   📊 Attempt {attempt}: Status = {status}, "
                              f"Progress = {progress.get('completed', 0)}/{progress.get('total', 0)}")

                        if status in ["completed", "failed"]:
                            break
                    else:
                        print(f"   ❌ Failed to get status: {response.status}")

                if attempt < max_attempts:
                    await asyncio.sleep(20)

            # Step 3: Get final results
            print(f"\n3️⃣ Getting final results...")

            async with session.get(f"{BASE_URL}/api/v1/jobs/{job_id}") as response:
                if response.status == 200:
                    final_status = await response.json()

                    print(f"   📋 Final status: {final_status['status']}")

                    # Show tools
                    tool_files = final_status.get('toolFiles', [])
                    if tool_files:
                        print(f"\n   🔧 Tools generated: {len(tool_files)}")
                        for tool in tool_files:
                            print(f"      - {tool['fileName']}")
                            print(f"        Description: {tool['description']}")
                            print(f"        Path: {tool['filePath']}")
                    else:
                        print(f"   ⚠️ No tools generated")

                    # Show failures
                    failures = final_status.get('failures', [])
                    if failures:
                        print(f"\n   ❌ Failures: {len(failures)}")
                        for failure in failures:
                            print(f"      - {failure['error']}")

                    # Show summary
                    summary = final_status.get('summary')
                    if summary:
                        print(f"\n   📊 Summary: {summary['successful']}/{summary['totalRequested']} successful")

                else:
                    print(f"   ❌ Failed to get final status: {response.status}")

        except aiohttp.ClientError as e:
            print(f"❌ Connection error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("🏁 Test completed!")


async def check_health():
    """Check if backend is running."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/api/v1/health") as response:
                if response.status == 200:
                    print("✅ Backend is healthy")
                    return True
                else:
                    print(f"❌ Backend health check failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("💡 Start the backend with: python -m app.main")
        return False


if __name__ == "__main__":
    async def main():
        print("🔍 Checking backend health...\n")
        if await check_health():
            print()

            for task_description in task_descriptions:
                await test_extract_and_submit(task_description)
        else:
            print("\n💡 Start the backend first:")
            print("   cd tool_generation_backend")
            print("   python -m app.main")

    asyncio.run(main())