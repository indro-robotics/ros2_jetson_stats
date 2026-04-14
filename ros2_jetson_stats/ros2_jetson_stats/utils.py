#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) 2020, Raffaello Bonghi <raffaello@rnext.it>
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING,
# BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import rclpy
from copy import deepcopy
from diagnostic_msgs.msg import DiagnosticStatus, KeyValue


def size_min(num, divider=1.0, n=0, start=''):
    if num >= divider * 1000.0:
        n += 1
        divider *= 1000.0
        return size_min(num, divider, n, start)
    else:
        vect = ['', 'K', 'M', 'G', 'T']
        idx = vect.index(start)
        return round(num / divider, 1), divider, vect[n + idx]


def strfdelta(tdelta, fmt):
    """Print delta time."""
    d = {"days": tdelta.days}
    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)


def other_status(hardware, jetson, version):
    """
    Generic information about jetson_clock and nvpmodel
    """
    values = []
    level = DiagnosticStatus.OK
    nvpmodel = jetson.nvpmodel
    text = ""
    if nvpmodel is not None:
        nvp_name = nvpmodel.name.replace('MODE_', '').replace('_', ' ')
        values += [KeyValue(key="NV Power-ID", value=str(nvpmodel.id)),
                   KeyValue(key="NV Power-Mode", value=str(nvp_name))]
        text += "NV Power[{id}] {name}".format(id=nvpmodel.id, name=nvp_name)

    jc = jetson.jetson_clocks
    if jc is not None:
        if jc.status in ["running", "inactive"]:
            level = DiagnosticStatus.OK
        elif "ing" in jc.status:
            level = DiagnosticStatus.WARN
        else:
            level = DiagnosticStatus.ERROR
        values += [KeyValue(key="jetson_clocks", value=str(jc.status))]
        values += [KeyValue(key="jetson_clocks on boot", value=str(jc.boot))]
        if text:
            text += " - "
        text += "JC {status}".format(status=jc.status)

    uptime_string = strfdelta(
        jetson.uptime, "{days} days {hours}:{minutes}:{seconds}")
    values += [KeyValue(key="Up Time", value=str(uptime_string))]
    values += [KeyValue(key="interval", value=str(jetson.interval))]
    values += [KeyValue(key="jtop", value=str(version))]

    status = DiagnosticStatus(
        level=level,
        name='jetson_stats board status',
        message=text,
        hardware_id=hardware,
        values=values)
    return status


def board_status(hardware, board, dgtype):
    """
    Board information and libraries installed
    """
    values = []
    for key, value in board.get('hardware', {}).items():
        values += [KeyValue(key=key, value=str(value))]
    for key, value in board.get('libraries', {}).items():
        values += [KeyValue(key="lib " + key, value=str(value))]

    jetpack = board.get('hardware', {}).get('Jetpack', 'unknown')
    d_board = DiagnosticStatus(
        name='jetson_stats {type} config'.format(type=dgtype),
        message='Jetpack {jetpack}'.format(jetpack=jetpack),
        hardware_id=hardware,
        values=values)
    return d_board


def disk_status(hardware, disk, dgtype):
    """
    Status disk
    """
    used = float(disk.get('used', 0))
    total = float(disk.get('total', 0))
    value = int(used / total * 100.0) if total else 0

    if value >= 90:
        level = DiagnosticStatus.ERROR
    elif value >= 70:
        level = DiagnosticStatus.WARN
    else:
        level = DiagnosticStatus.OK

    d_board = DiagnosticStatus(
        level=level,
        name='jetson_stats {type} disk'.format(type=dgtype),
        message="{0:2.1f}GB/{1:2.1f}GB".format(used, total),
        hardware_id=hardware,
        values=[
            KeyValue(key="Used", value=str(disk.get('used', 0))),
            KeyValue(key="Total", value=str(disk.get('total', 0))),
            KeyValue(key="Unit", value="GB")])
    return d_board


def cpu_status(hardware, name, cpu):
    """
    Decode a cpu stats
    """
    message = 'OFF'
    values = []
    if cpu:
        if 'idle' in cpu:
            val = 100 - cpu['idle']
            message = '{val}%'.format(val=val)
            freq = cpu.get('freq', {}).get('cur', '0')
            values = [
                KeyValue(key="Val", value=str(val)),
                KeyValue(key="Freq", value=str(freq)),
                KeyValue(key="Unit", value="khz")]

        if 'governor' in cpu and cpu['governor']:
            values += [KeyValue(key="Governor", value=str(cpu['governor']))]

        if 'model' in cpu and cpu['model']:
            values += [KeyValue(key="Model", value=str(cpu['model']))]

    d_cpu = DiagnosticStatus(
        name='jetson_stats cpu {name}'.format(name=name),
        message=message,
        hardware_id=hardware,
        values=values)
    return d_cpu


def gpu_status(hardware, name, gpu):
    """
    Decode and build a diagnostic status message
    """
    load = gpu.get('status', {}).get('load', 0)
    freq = gpu.get('freq', '0')
    d_gpu = DiagnosticStatus(
        name='jetson_stats gpu {name}'.format(name=name),
        message='{val}%'.format(val=load),
        hardware_id=hardware,
        values=[KeyValue(key='Val', value=str(load)),
                KeyValue(key='Freq', value=str(freq)),
                KeyValue(key='Unit', value="khz")])
    return d_gpu


def fan_status(hardware, name, fan):
    """
    Fan speed and type of control
    """
    d_fan = DiagnosticStatus(
        name='jetson_stats {name} fan'.format(name=name),
        message='speed={speed}%'.format(speed=fan.get('speed', '0')),
        hardware_id=hardware,
        values=[
            KeyValue(key='Mode', value=str(fan.get('profile', 'unknown'))),
            KeyValue(key="Speed", value=str(fan.get('speed', '0'))),
            KeyValue(key="Control", value=str(fan.get('control', 'unknown'))),
        ])
    return d_fan


def ram_status(hardware, ram, dgtype):
    """
    Make a RAM diagnostic status message
    """
    lfb_status = ram.get('lfb', 0)
    tot_ram, divider, unit_name = size_min(ram.get('tot', 0), start='K')
    used = ram.get('used', 0)

    d_ram = DiagnosticStatus(
        name='jetson_stats {type} ram'.format(type=dgtype),
        message='{use:2.1f}{unit_ram}B/{tot:2.1f}{unit_ram}B (lfb {nblock}x4MB)'.format(
            use=used / divider if divider else 0,
            unit_ram=unit_name,
            tot=tot_ram,
            nblock=lfb_status),
        hardware_id=hardware,
        values=[
            KeyValue(key="Use", value=str(used)),
            KeyValue(key="Shared", value=str(ram.get('shared', 0))),
            KeyValue(key="Total", value=str(ram.get('tot', 0))),
            KeyValue(key="Unit", value='K'),
            KeyValue(key="lfb-nblock", value=str(lfb_status)),
            KeyValue(key="lfb-size", value=str(4)),
            KeyValue(key="lfb-unit", value=str('M'))])
    return d_ram


def swap_status(hardware, swap, dgtype):
    """
    Make a swap diagnostic message
    """
    swap_cached = swap.get('cached', '0')
    tot_swap, divider, unit = size_min(swap.get('tot', 0), start='K')
    used = swap.get('used', 0)
    message = '{use}{unit_swap}B/{tot}{unit_swap}B (cached {cached}KB)'.format(
        use=used / divider if divider else 0,
        tot=tot_swap,
        unit_swap=unit,
        cached=swap_cached)

    d_swap = DiagnosticStatus(
        name='jetson_stats {type} swap'.format(type=dgtype),
        message=message,
        hardware_id=hardware,
        values=[
            KeyValue(key="Use", value=str(used)),
            KeyValue(key="Total", value=str(swap.get('tot', 0))),
            KeyValue(key="Unit", value='K'),
            KeyValue(key="Cached-Size", value=str(swap_cached)),
            KeyValue(key="Cached-Unit", value='K')])
    return d_swap


def power_status(hardware, power):
    """
    Make a Power diagnostic message
    """
    values = []
    rail_map = power.get('rail', {}) if isinstance(power, dict) else {}
    tot = power.get('tot', {}) if isinstance(power, dict) else {}

    for rail_name in sorted(rail_map):
        value = rail_map[rail_name]
        watt_name = rail_name.replace("VDD_", "").replace("POM_", "").replace("_", " ")
        curr = value.get('curr', 0) if isinstance(value, dict) else 0
        avg = value.get('avg', 0) if isinstance(value, dict) else 0
        values += [
            KeyValue(key="Name", value=watt_name),
            KeyValue(key="Current Power", value=str(int(curr) if curr is not None else 0)),
            KeyValue(key="Average Power", value=str(int(avg) if avg is not None else 0))
        ]

    curr = tot.get('curr')
    if curr is None:
        curr = tot.get('cur', 0)
    avg = tot.get('avg', 0)

    d_volt = DiagnosticStatus(
        name='jetson_stats power',
        message='curr={curr}mW avg={avg}mW'.format(
            curr=int(curr) if curr is not None else 0,
            avg=int(avg) if avg is not None else 0),
        hardware_id=hardware,
        values=values)
    return d_volt


def temp_status(hardware, temp, level_options):
    """
    Make a temperature diagnostic message
    """
    values = []
    level = DiagnosticStatus.OK
    list_options = sorted(level_options.keys(), reverse=True)
    max_temp = 20

    for key, value in temp.items():
        if not value['online']:
            pass
        values += [KeyValue(key=key, value=str(value['temp']))]
        if value['temp'] > max_temp:
            max_temp = value['temp']

    for th in list_options:
        if max_temp >= th:
            level = level_options[th]
            break

    if level is not DiagnosticStatus.OK:
        max_temp_names = []
        for key, value in temp.items():
            if value['temp'] >= th:
                max_temp_names += [key]
        message = '[' + ', '.join(max_temp_names) + '] are more than {temp} C'.format(temp=th)
    else:
        message = '{n_temp} temperatures reads'.format(n_temp=len(temp))

    d_temp = DiagnosticStatus(
        level=level,
        name='jetson_stats temp',
        message=message,
        hardware_id=hardware,
        values=values)
    return d_temp


def emc_status(hardware, emc, dgtype):
    """
    Make a EMC diagnostic message
    """
    d_emc = DiagnosticStatus(
        name='jetson_stats {type} emc'.format(type=dgtype),
        message='{val}%'.format(val=emc.get('val', 0)),
        hardware_id=hardware,
        values=[
            KeyValue(key='Val', value=str(emc.get('val', 0))),
            KeyValue(key="Freq", value=str(emc.get('cur', 0))),
            KeyValue(key="Unit", value="khz")])
    return d_emc
# EOF
