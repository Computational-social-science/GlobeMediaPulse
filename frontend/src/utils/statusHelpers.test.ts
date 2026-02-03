import { describe, it, expect } from 'vitest';
import {
    getStatusColor,
    getThreadStatusColor,
    getSystemIconClass,
    getSystemDotClass,
    getSystemSlotClass,
    getSecondarySlotClass,
    getSystemTitleClass
} from '@/utils/statusHelpers';

describe('statusHelpers', () => {
    describe('getStatusColor', () => {
        it('should return status-text-ok for OK statuses', () => {
            expect(getStatusColor('ok')).toBe('status-text-ok');
            expect(getStatusColor('ONLINE')).toBe('status-text-ok');
            expect(getStatusColor('Active')).toBe('status-text-ok');
        });

        it('should return status-text-warn for Warning statuses', () => {
            expect(getStatusColor('warning')).toBe('status-text-warn');
            expect(getStatusColor('DEGRADED')).toBe('status-text-warn');
            expect(getStatusColor('starting')).toBe('status-text-warn');
        });

        it('should return status-text-error for Error statuses', () => {
            expect(getStatusColor('error')).toBe('status-text-error');
            expect(getStatusColor('OFFLINE')).toBe('status-text-error');
            expect(getStatusColor('failed')).toBe('status-text-error');
        });

        it('should return status-text-neutral for other or empty statuses', () => {
            expect(getStatusColor('unknown')).toBe('status-text-neutral');
            expect(getStatusColor('')).toBe('status-text-neutral');
            expect(getStatusColor(undefined)).toBe('status-text-neutral');
        });
    });

    describe('getSystemDotClass', () => {
        it('should return correct dot class for system statuses', () => {
            expect(getSystemDotClass('ONLINE')).toBe('status-dot-ok');
            expect(getSystemDotClass('DEGRADED')).toBe('status-dot-warn');
            expect(getSystemDotClass('OFFLINE')).toBe('status-dot-error');
            expect(getSystemDotClass('UNKNOWN')).toBe('status-dot-neutral');
        });
    });

    describe('getSystemSlotClass', () => {
        it('should return correct background class for system statuses', () => {
            expect(getSystemSlotClass('ONLINE')).toBe('status-bg-ok');
            expect(getSystemSlotClass('DEGRADED')).toBe('status-bg-warn');
            expect(getSystemSlotClass('OFFLINE')).toBe('status-bg-error');
            expect(getSystemSlotClass('OTHER')).toBe('sidebar-panel-sub sidebar-text-muted');
        });
    });

    describe('getSystemTitleClass', () => {
        it('should return correct title class for system statuses', () => {
            expect(getSystemTitleClass('ONLINE')).toBe('status-text-ok');
            expect(getSystemTitleClass('DEGRADED')).toBe('status-text-warn');
            expect(getSystemTitleClass('OFFLINE')).toBe('status-text-error');
            expect(getSystemTitleClass('OTHER')).toBe('sidebar-text-muted');
        });
    });
});
