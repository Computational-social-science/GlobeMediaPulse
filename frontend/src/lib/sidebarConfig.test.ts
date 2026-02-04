import { describe, it, expect } from 'vitest';
import {
  SIDEBAR_STORAGE_KEY,
  getDefaultSidebarConfig,
  normalizeSidebarConfig,
  moveSidebarItem,
  addSidebarGroup,
  setSidebarGroupCollapsed,
  tidySidebarConfig,
  loadSidebarConfig,
  saveSidebarConfig,
  clearSidebarConfig
} from '@stores';

type SidebarGroup = { id: string; title: string; items: string[]; collapsed?: boolean };

const createStorage = (shouldThrow = false) => {
  const store = new Map<string, string>();
  return {
    getItem: (key: string) => {
      if (shouldThrow) throw new Error('getItem failed');
      return store.get(key) ?? null;
    },
    setItem: (key: string, value: string) => {
      if (shouldThrow) throw new Error('setItem failed');
      store.set(key, value);
    },
    removeItem: (key: string) => {
      if (shouldThrow) throw new Error('removeItem failed');
      store.delete(key);
    }
  };
};

describe('sidebar config utilities', () => {
  it('normalizes empty config to default', () => {
    const normalized = normalizeSidebarConfig(null);
    expect(normalized.groups[0].items).toEqual(getDefaultSidebarConfig().groups[0].items);
  });

  it('deduplicates and restores missing items', () => {
    const normalized = normalizeSidebarConfig({
      version: 1,
      groups: [
        { id: 'custom', title: 'Custom', items: ['gde', 'gde', 'autoheal', 'invalid'] }
      ]
    });
    expect(normalized.groups[0].items).toContain('gde');
    expect(normalized.groups[0].items).toContain('autoheal');
    expect(normalized.groups[0].items).toContain('status');
    expect(normalized.groups[0].items).not.toContain('invalid');
  });

  it('creates a core group when groups array is empty', () => {
    const normalized = normalizeSidebarConfig({ version: 1, groups: [] });
    expect(normalized.groups.length).toBeGreaterThan(0);
    expect(normalized.groups[0].id).toBe('core');
  });

  it('normalizes malformed group fields safely', () => {
    const normalized = normalizeSidebarConfig({
      groups: [
        {
          id: 123,
          title: '   ',
          collapsed: 'yes',
          items: [null, 1, 'status', 'gde']
        }
      ]
    });
    expect(normalized.groups[0].id).toBe('group-1');
    expect(normalized.groups[0].title).toBe('Group 1');
    expect(normalized.groups[0].collapsed).toBe(true);
    expect(normalized.groups[0].items).toContain('status');
    expect(normalized.groups[0].items).toContain('gde');
  });

  it('handles groups with non-array items', () => {
    const normalized = normalizeSidebarConfig({ groups: [{ id: 'x', title: 'X', items: 'nope' }] });
    expect(normalized.groups[0].items).toContain('status');
  });

  it('moves items across groups', () => {
    const defaultConfig = getDefaultSidebarConfig();
    const { config, groupId } = addSidebarGroup(defaultConfig, 'Ops');
    const moved = moveSidebarItem(config, {
      itemId: 'autoheal',
      fromGroupId: config.groups[0].id,
      toGroupId: groupId,
      toIndex: 0
    });
    expect(moved.groups.find((group: SidebarGroup) => group.id === groupId)?.items).toEqual(['autoheal']);
  });

  it('moves items down within the same group', () => {
    const defaultConfig = getDefaultSidebarConfig();
    const groupId = defaultConfig.groups[0].id;
    const moved = moveSidebarItem(defaultConfig, {
      itemId: 'status',
      fromGroupId: groupId,
      toGroupId: groupId,
      toIndex: 3
    });
    expect(moved.groups[0].items[moved.groups[0].items.length - 1]).toBe('status');
  });

  it('ignores invalid move payloads', () => {
    const cfg = getDefaultSidebarConfig();
    const moved = moveSidebarItem(cfg, { itemId: 'status', fromGroupId: 'missing', toGroupId: 'core', toIndex: 0 });
    expect(moved.groups[0].items).toEqual(cfg.groups[0].items);
  });

  it('keeps unrelated groups unchanged during moves', () => {
    const base = {
      version: 1,
      groups: [
        { id: 'core', title: 'Core', items: ['status', 'gde', 'autoheal'] },
        { id: 'ops', title: 'Ops', items: [] },
        { id: 'keep', title: 'Keep', items: [] }
      ]
    };
    const moved = moveSidebarItem(base, {
      itemId: 'gde',
      fromGroupId: 'core',
      toGroupId: 'ops',
      toIndex: 0
    });
    expect(moved.groups.find((g: SidebarGroup) => g.id === 'keep')?.items).toEqual([]);
  });

  it('allocates a unique group id when adding groups', () => {
    const base = {
      version: 1,
      groups: [
        { id: 'group-1', title: 'Group 1', items: ['status'] },
        { id: 'group-2', title: 'Group 2', items: ['gde'] }
      ]
    };
    const { groupId } = addSidebarGroup(base, 'More');
    expect(groupId).toBe('group-3');
  });

  it('toggles group collapsed state', () => {
    const defaultConfig = getDefaultSidebarConfig();
    const groupId = defaultConfig.groups[0].id;
    const collapsed = setSidebarGroupCollapsed(defaultConfig, groupId, true);
    expect(collapsed.groups[0].collapsed).toBe(true);
  });

  it('tidies config by removing empty groups', () => {
    const config = {
      version: 1,
      groups: [
        { id: 'core', title: 'Core', items: ['status', 'gde'] },
        { id: 'empty', title: '   ', items: [] }
      ]
    };
    const tidied = tidySidebarConfig(config);
    expect(tidied.groups.length).toBe(1);
    expect(tidied.groups[0].title).toBe('Core');
  });

  it('reads and writes storage safely', () => {
    const storage = createStorage(false);
    const defaultConfig = getDefaultSidebarConfig();
    const saved = saveSidebarConfig(storage as Storage, defaultConfig);
    expect(saved).toBe(true);
    expect(storage.getItem(SIDEBAR_STORAGE_KEY)).not.toBeNull();
    const loaded = loadSidebarConfig(storage as Storage);
    expect(loaded?.groups[0].items).toEqual(defaultConfig.groups[0].items);
    const cleared = clearSidebarConfig(storage as Storage);
    expect(cleared).toBe(true);
  });

  it('handles storage failures gracefully', () => {
    const storage = createStorage(true);
    expect(loadSidebarConfig(storage as Storage)).toBeNull();
    expect(saveSidebarConfig(storage as Storage, getDefaultSidebarConfig())).toBe(false);
    expect(clearSidebarConfig(storage as Storage)).toBe(false);
  });
});
