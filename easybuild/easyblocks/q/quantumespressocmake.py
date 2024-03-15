##
# Copyright 2009-2023 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# https://github.com/easybuilders/easybuild
#
# EasyBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EasyBuild.  If not, see <http://www.gnu.org/licenses/>.
##
"""
EasyBuild support for Quantum ESPRESSO, implemented as an easyblock

@author: Davide Grassano (CECAM, EPFL)
"""
import os
import re

import easybuild.tools.toolchain as toolchain
from easybuild.framework.easyconfig import CUSTOM
from easybuild.tools import LooseVersion
from easybuild.tools.build_log import EasyBuildError
from easybuild.tools.modules import get_software_root
from easybuild.tools.run import run_cmd

from easybuild.easyblocks.generic.cmakemake import CMakeMake


class EB_QuantumESPRESSOcmake(CMakeMake):
    """Support for building and installing Quantum ESPRESSO."""

    TEST_SUITE_DIR = "test-suite"

    @staticmethod
    def extra_options():
        """Custom easyconfig parameters for Quantum ESPRESSO."""
        extra_vars = {
            'with_cuda': [False, "Enable CUDA support", CUSTOM],
            'with_scalapack': [True, "Enable ScaLAPACK support", CUSTOM],
            'with_fox': [False, "Enable FoX support", CUSTOM],
            'with_gipaw': [True, "Enable GIPAW support", CUSTOM],
            'with_d3q': [False, "Enable D3Q support", CUSTOM],
            'with_qmcpack': [False, "Enable QMCPACK support", CUSTOM],
            'test_suite_nprocs': [1, "Number of processors to use for the test suite", CUSTOM],
            'test_suite_allow_failures': [[
                'test_qe_xclib_',  # 7.3.1:  https://gitlab.com/QEF/q-e/-/issues/640
                '--hp_',  # 7.3.1:  Broken testsuite (https://gitlab.com/QEF/q-e/-/issues/665)
                '--ph_',  # 7.3.1:  Broken testsuite (https://gitlab.com/QEF/q-e/-/issues/665)
                '--epw_',  # 7.3.1:  Broken testsuite (https://gitlab.com/QEF/q-e/-/issues/665)
                '--tddfpt_',  # 7.3.1:  Broken testsuite (https://gitlab.com/QEF/q-e/-/issues/665)
            ], "List of test suite targets that are allowed to fail (name can partially match)", CUSTOM],
            'test_suite_threshold': [
                0.97,
                "Threshold for test suite success rate (does count also allowed failures)",
                CUSTOM
                ],
            'test_suite_max_failed': [0, "Maximum number of failing tests (does not count allowed failures)", CUSTOM],
        }
        return CMakeMake.extra_options(extra_vars)

    def __init__(self, *args, **kwargs):
        """Add extra config options specific to Quantum ESPRESSO."""
        super(EB_QuantumESPRESSOcmake, self).__init__(*args, **kwargs)

        self.install_subdir = "qe-%s" % self.version

        self.check_bins = []

    def _add_toolchains_opts(self):
        """Enable toolchain options for Quantum ESPRESSO."""
        self._add_mpi()
        self._add_openmp()
        self._add_cuda()

    def _add_libraries(self):
        """Enable external libraries for Quantum ESPRESSO."""
        self._add_scalapack()
        self._add_fox()
        self._add_libxc()
        self._add_elpa()
        self._add_hdf5()

    def _add_plugins(self):
        """Enable plugins for Quantum ESPRESSO."""
        plugins = []
        plugins += self._add_gipaw()
        plugins += self._add_d3q()
        plugins += self._add_qmcpack()
        if plugins:
            self.cfg.update('configopts', '-DQE_ENABLE_PLUGINS="%s"' % ';'.join(plugins))

    def _add_mpi(self):
        """Enable MPI for Quantum ESPRESSO."""
        if self.toolchain.options.get('usempi', False):
            self.cfg.update('configopts', '-DENABLE_MPI=ON')

    def _add_openmp(self):
        """Enable OpenMP for Quantum ESPRESSO."""
        if self.toolchain.options.get('openmp', False):
            self.cfg.update('configopts', '-DENABLE_OPENMP=ON')

    def _add_cuda(self):
        """Enable CUDA for Quantum ESPRESSO."""
        if self.cfg.get('with_cuda', False):
            self.cfg.update('configopts', '-DQE_ENABLE_CUDA=ON')
            self.cfg.update('configopts', '-DQE_ENABLE_OPENACC=ON')

    def _add_scalapack(self):
        """Enable ScaLAPACK for Quantum ESPRESSO."""
        if self.cfg.get('with_scalapack', False):
            if not self.toolchain.options.get('usempi', False):
                raise EasyBuildError("ScaLAPACK support requires MPI")
            self.cfg.update('configopts', '-DQE_ENABLE_SCALAPACK=ON')

    def _add_fox(self):
        """Enable FoX for Quantum ESPRESSO."""
        if self.cfg.get('with_fox', False):
            self.cfg.update('configopts', '-DQE_ENABLE_FOX=ON')

    def _add_hdf5(self):
        """Enable HDF5 for Quantum ESPRESSO."""
        if get_software_root("HDF5"):
            self.cfg.update('configopts', '-DQE_ENABLE_HDF5=ON')

    def _add_libxc(self):
        """Enable LibXC for Quantum ESPRESSO."""
        if get_software_root("libxc"):
            self.cfg.update('configopts', '-DQE_ENABLE_LIBXC=ON')

    def _add_elpa(self):
        """Enable ELPA for Quantum ESPRESSO."""
        if get_software_root("ELPA"):
            if not self.cfg.get('with_scalapack', False):
                raise EasyBuildError("ELPA support requires ScaLAPACK")
            if LooseVersion(self.version) == LooseVersion('7.3') and self.toolchain.options.get('openmp', False):
                raise EasyBuildError("QE 7.3 with cmake does not support ELPA with OpenMP")
            self.cfg.update('configopts', '-DQE_ENABLE_ELPA=ON')

    def _add_gipaw(self):
        """Enable GIPAW for Quantum ESPRESSO."""
        res = []
        if self.cfg.get('with_gipaw', False):
            if LooseVersion(self.version) == LooseVersion('7.3.1'):
                # See issue: https://github.com/dceresoli/qe-gipaw/issues/19
                raise EasyBuildError("GIPAW will fail to compile in QE 7.3.1")
            res = ['gipaw']
            self.check_bins += ['gipaw.x']
        return res

    def _add_d3q(self):
        """Enable D3Q for Quantum ESPRESSO."""
        res = []
        if self.cfg.get('with_d3q', False):
            if LooseVersion(self.version) > LooseVersion('7.0'):
                # See issues:
                # https://gitlab.com/QEF/q-e/-/issues/666
                # https://github.com/anharmonic/d3q/issues/13
                raise EasyBuildError("D3Q is not supported in QE 7.0+")
            res = ['d3q']
            self.check_bins += [
                'd3_asr3.x', 'd3_lw.x', 'd3_q2r.x', 'd3_qq2rr.x', 'd3q.x', 'd3_r2q.x', 'd3_recenter.x',
                'd3_sparse.x', 'd3_sqom.x', 'd3_tk.x'
                ]
        return res

    def _add_qmcpack(self):
        """Enable QMCPACK for Quantum ESPRESSO."""
        res = []
        if self.cfg.get('with_qmcpack', False):
            res = ['pw2qmcpack']
            self.check_bins += ['pw2qmcpack.x']
        return res

    def configure_step(self):
        """Custom configuration procedure for Quantum ESPRESSO."""

        if LooseVersion(self.version) < LooseVersion('7.3'):
            raise EasyBuildError("EB QuantumEspresso cmake is implemented for versions >= 7.3")
        
        comp_fam = self.toolchain.comp_family()

        self._add_toolchains_opts()
        self._add_libraries()
        self._add_plugins()

        # Enable/configure test suite
        nprocs = self.cfg.get('test_suite_nprocs', 1)
        self.cfg.update('configopts', '-DQE_ENABLE_TEST=ON')
        self.cfg.update('configopts', '-DTESTCODE_NPROCS=%d' % nprocs)

        # Change format of timings to seconds only (from d/h/m/s)
        self.cfg.update('configopts', '-DQE_CLOCK_SECONDS=ON')

        # Needed to avoid a DSO missing from command line linking error with the Intel toolchain
        # https://gitlab.com/QEF/q-e/-/issues/667
        if self.cfg.get('build_shared_libs', False) and comp_fam == toolchain.INTELCOMP:
            ldflags = os.environ.get('LDFLAGS', '')
            ldflags += ' -Wl,--copy-dt-needed-entries '
            os.environ['LDFLAGS'] = ldflags
 
        super(EB_QuantumESPRESSOcmake, self).configure_step()

    def test_step(self):
        """
        Test the compilation using Quantum ESPRESSO's test suite.
        ctest -j NCONCURRENT (NCONCURRENT = max (1, PARALLEL / NPROCS))
        """

        thr = self.cfg.get('test_suite_threshold', 0.97)
        nprocs = self.cfg.get('test_suite_nprocs', 1)
        concurrent = max(1, self.cfg.get('parallel', 1) // nprocs)
        allow_fail = self.cfg.get('test_suite_allow_failures', [])

        cmd = ' '.join([
            'ctest',
            '-j%d' % concurrent,
            '--output-on-failure',
        ])

        (out, _) = run_cmd(cmd, log_all=False, log_ok=False, simple=False, regexp=False)

        # Example output:
        # 74% tests passed, 124 tests failed out of 481
        rgx = r'^ *(?P<perc>\d+)% tests passed, +(?P<failed>\d+) +tests failed out of +(?P<total>\d+)'
        mch = re.search(rgx, out, re.MULTILINE)
        if not mch:
            raise EasyBuildError("Failed to parse test suite output")
        
        perc = int(mch.group('perc')) / 100
        num_fail = int(mch.group('failed'))
        total = int(mch.group('total'))
        passed = total - num_fail
        failures = []  # list of tests that failed, to be logged at the end


        # Example output for reported failures:
        # 635/635 Test #570: system--epw_wfpt-correctness ......................................***Failed    3.52 sec
        self.log.debug("Test suite output:")
        self.log.debug(out)
        for line in out.splitlines():
            if '***Failed' in line:
                for allowed in allow_fail:
                    if allowed in line:
                        self.log.info('Ignoring failure: %s' % line)
                        break
                else:
                    failures.append(line)
                self.log.warning(line)

        # Allow for flaky tests (eg too strict thresholds on results for structure relaxation)
        num_fail = len(failures)
        num_fail_thr = self.cfg.get('test_suite_max_failed', 0)
        # perc = spass / max(stot, 1)
        self.log.info("Total tests passed %d out of %d  (%.2f%%)" % (passed, total, perc * 100))
        if perc < thr:
            raise EasyBuildError(
                "Test suite failed with less than %.2f %% (%.2f) success rate" % (thr * 100, perc * 100)
                )
        if num_fail > num_fail_thr:
            raise EasyBuildError(
                "Test suite failed with more than %d failures %d" % (num_fail_thr, num_fail)
                )

        return out

    def sanity_check_step(self):
        """Custom sanity check for Quantum ESPRESSO."""

        targets = self.cfg['buildopts'].split()

        # Condition for all targets being build 'make'  or 'make all_currents'
        all_cond = len(targets) == 0 or 'all_currents' in targets
        pwall_cond = 'pwall' in targets


        # Standard binaries
        if all_cond or 'cp' in targets :
            self.check_bins += ["cp.x", "cppp.x", "manycp.x", "wfdd.x"]

        if all_cond or 'epw' in targets:
            self.check_bins += ["epw.x"]

        if all_cond or 'gwl' in targets:
            self.check_bins += [
                "abcoeff_to_eps.x", "bse_main.x", "graph.x", "gww_fit.x", "gww.x", "head.x", "memory_pw4gww.x",
                "pw4gww.x", "simple_bse.x", "simple_ip.x", "simple.x"
                ]

        if all_cond or 'hp' in targets:
            self.check_bins += ["hp.x"]

        if all_cond or 'ld1' in targets:
            self.check_bins += ["ld1.x"]

        if all_cond or pwall_cond or 'neb' in targets:
            self.check_bins += ["neb.x", "path_interpolation.x"]

        if all_cond or pwall_cond or 'ph' in targets:
            self.check_bins += [
                "alpha2f.x", "dynmat.x", "fd_ef.x", "fd.x", "lambda.x", "phcg.x", "postahc.x", "q2r.x", "dvscf_q2r.x",
                "epa.x", "fd_ifc.x", "fqha.x", "matdyn.x", "ph.x", "q2qstar.x"
                ]

        if all_cond or pwall_cond or 'pp' in targets:
            self.check_bins += [
                "average.x", "dos_sp.x", "ef.x", "fermi_int_0.x", "fermi_proj.x", "fs.x", "molecularpdos.x",
                "pawplot.x", "plotband.x", "plotrho.x", "ppacf.x", "pp.x", "pw2bgw.x", "pw2gt.x", "pw2wannier90.x",
                "wannier_ham.x", "wfck2r.x", "bands.x", "dos.x", "epsilon.x", "fermi_int_1.x", "fermi_velocity.x",
                "initial_state.x", "open_grid.x", "plan_avg.x", "plotproj.x", "pmw.x", "pprism.x", "projwfc.x",
                "pw2critic.x", "pw2gw.x", "sumpdos.x", "wannier_plot.x"
                ]

        if all_cond or pwall_cond or 'pw' in targets:
            self.check_bins += [
                "cell2ibrav.x", "ev.x", "ibrav2cell.x", "kpoints.x", "pwi2xsf.x", "pw.x", "scan_ibrav.x"
                ]

        if all_cond or pwall_cond or 'pwcond' in targets:
            self.check_bins += ["pwcond.x"]

        if all_cond or 'tddfpt' in targets:
            self.check_bins += [
                "turbo_davidson.x", "turbo_eels.x", "turbo_lanczos.x", "turbo_magnon.x", "turbo_spectrum.x"
                ]

        if all_cond or 'upf' in targets:
            self.check_bins += ["upfconv.x", "virtual_v2.x"]

        if all_cond or 'xspectra' in targets:
            self.check_bins += ["molecularnexafs.x", "spectra_correction.x", "xspectra.x"]

        custom_paths = {
            'files': [os.path.join('bin', x) for x in self.check_bins],
            'dirs': []
        }

        super(EB_QuantumESPRESSOcmake, self).sanity_check_step(custom_paths=custom_paths)
