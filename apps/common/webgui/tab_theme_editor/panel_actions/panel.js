/**
 * =============================================================================
 * Process Name: Windows Web Interface - Theme Editor Actions Panel
 * =============================================================================
 * Description:
 *   Модуль панели действий (тулбара): сохранение дочерней темы, создание
 *   дочерней темы на базе стандартной, сброс к родителю, удаление, переименование,
 *   экспорт/импорт JSON и копирование CSS.
 *
 * File: panel_actions/panel.js
 * Project: ai-windows-admin
 * Package: apps/windows/api/webgui/tab_theme_editor/panel_actions
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-19 18:02:00
 * =============================================================================
 */

import { showToast, t } from '../common/ui_utils.js';
import { PRESETS, loadPreset, getPreset } from '../panel_presets/panel.js';
import {
  collectTokensFromUI,
  collectFullStateFromUI,
  applyStateToUI,
  generateCssString
} from '../panel_tokens/panel.js';

/**
 * Загружает текущее сохраненное состояние темы или активный пресет.
 * @param {Function} onUpdate - Колбэк обновления превью.
 */
export function loadCurrentThemeState(onUpdate) {
  const presetSelect = document.getElementById('theme-preset-select');
  const savedMode = window.themeEngine ? window.themeEngine.getSavedMode() : 'theme-dark-slate';
  const targetPreset = presetSelect && presetSelect.value ? presetSelect.value : savedMode;

  loadPreset(targetPreset, () => {
    if (window.themeEngine) {
      window.themeEngine.previewTheme(targetPreset);
    }
    if (typeof onUpdate === 'function') onUpdate();
  });
}

/**
 * Отрисовывает предпросмотр цветовых кружков (swatches) выбранной базовой темы в модалке создания.
 * @param {string} baseThemeId - ID базовой темы.
 */
function renderBaseThemeSwatches(baseThemeId) {
  const container = document.getElementById('child-theme-base-swatches');
  if (!container) return;

  const preset = getPreset(baseThemeId);
  const c = preset?.colors || {};
  const swatches = [
    { color: c.bgBase, label: t('ui.thm.txt_7bbb3019', 'Фон') },
    { color: c.bgSurface, label: t('ui.thm.txt_63d2f25c', 'Карточка') },
    { color: c.bgElevated, label: t('ui.thm.txt_11a013e2', 'Панель') },
    { color: c.textPrimary, label: t('ui.thm.txt_0b2b38e4', 'Текст') },
    { color: c.accent, label: t('ui.thm.txt_a9c64f76', 'Акцент') },
    { color: c.success, label: t('ui.thm.txt_3d9aab48', 'Успех') },
  ].filter((s) => Boolean(s.color));

  container.innerHTML = '';
  swatches.forEach(({ color, label }) => {
    const chip = document.createElement('span');
    chip.className = 'd-inline-flex align-items-center gap-1 border rounded px-1.5 py-0.5 small font-monospace';
    chip.title = `${label}: ${color}`;

    const dot = document.createElement('span');
    dot.className = 'd-inline-block rounded-circle border';
    dot.style.width = '12px';
    dot.style.height = '12px';
    dot.style.backgroundColor = color;

    const text = document.createElement('span');
    text.textContent = label;
    chip.appendChild(dot);
    chip.appendChild(text);
    container.appendChild(chip);
  });
}

/**
 * Открывает модальное окно создания своей темы на основе любой существующей темы.
 * @param {string} [defaultParentId] - ID базовой родительской темы.
 */
export function openCreateChildModal(defaultParentId) {
  const presetSelect = document.getElementById('theme-preset-select');
  const currentKey = defaultParentId || presetSelect?.value || 'theme-dark-slate';
  const parentId = currentKey;

  const parentTheme = window.themeEngine?.getTheme(parentId) || window.themeEngine?.getTheme('theme-dark-slate');
  const parentName = parentTheme?.name || parentId;

  // Наполнение селектора базовых тем в модальном окне (стандартные + пользовательские)
  const parentSelect = document.getElementById('child-theme-parent-select');
  if (parentSelect && window.themeEngine) {
    const customThemes = window.themeEngine.getCustomThemes();
    const standardThemes = window.themeEngine.getStandardThemes();
    const darkThemes = standardThemes.filter((x) => x.category === 'dark');
    const lightThemes = standardThemes.filter((x) => x.category === 'light');

    let optionsHtml = '';
    if (customThemes.length > 0) {
      optionsHtml += `<optgroup label="${t('ui.thm.optCustomThemes', 'Пользовательские темы')}">\n`;
      optionsHtml += customThemes
        .map((x) => `  <option value="${x.id}"${x.id === parentId ? ' selected' : ''}>${x.name}</option>`)
        .join('\n');
      optionsHtml += '\n</optgroup>\n';
    }
    if (lightThemes.length > 0) {
      optionsHtml += `<optgroup label="${t('ui.thm.optLightThemes', 'Светлые темы')}">\n`;
      optionsHtml += lightThemes
        .map((x) => `  <option value="${x.id}"${x.id === parentId ? ' selected' : ''}>${x.name}</option>`)
        .join('\n');
      optionsHtml += '\n</optgroup>\n';
    }
    if (darkThemes.length > 0) {
      optionsHtml += `<optgroup label="${t('ui.thm.optDarkThemes', 'Тёмные темы')}">\n`;
      optionsHtml += darkThemes
        .map((x) => `  <option value="${x.id}"${x.id === parentId ? ' selected' : ''}>${x.name}</option>`)
        .join('\n');
      optionsHtml += '\n</optgroup>\n';
    }
    parentSelect.innerHTML = optionsHtml;
    parentSelect.value = parentId;
  }

  renderBaseThemeSwatches(parentId);

  const keepEditsCb = document.getElementById('child-theme-keep-edits');
  if (keepEditsCb) {
    keepEditsCb.checked = true;
  }

  // Предзаполнение названия
  const nameInput = document.getElementById('child-theme-name-input');
  if (nameInput) {
    nameInput.value = `${parentName} (${t('ui.thm.myCopySuffix', 'Моя тема')})`;
    nameInput.dataset.autoFilled = 'true';
  }

  const descInput = document.getElementById('child-theme-desc-input');
  if (descInput) {
    descInput.value = `${t('ui.thm.basedOnPrefix', 'Собрана на основе')}: ${parentName}`;
    descInput.dataset.autoFilled = 'true';
  }

  const modalEl = document.getElementById('themeCreateChildModal');
  if (modalEl && window.bootstrap) {
    const modalInstance = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modalInstance.show();
  }
}

/**
 * Подключает слушатели событий к кнопкам действий тулбара.
 * @param {Function} onUpdate - Колбэк обновления превью.
 */
export function bindActions(onUpdate) {
  const presetSelect = document.getElementById('theme-preset-select');

  // Кнопка Сохранить тему
  const btnSave = document.getElementById('theme-btn-save');
  if (btnSave) {
    btnSave.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : 'theme-dark-slate';
      const isChild = window.themeEngine?.isChildTheme(selectedPreset);

      if (isChild) {
        // Сохранение в существующую дочернюю тему
        const tokens = collectTokensFromUI();
        const state = collectFullStateFromUI();
        const updated = window.themeEngine.updateChildTheme(selectedPreset, {
          tokens,
          settings: state,
        });
        showToast('Тема оформления', `Изменения успешно сохранены в дочернюю тему «${updated.name}»!`, 'success');
      } else {
        // Стандартные темы защищены от изменений — предлагаем создать дочернюю тему
        openCreateChildModal(selectedPreset);
      }
    });
  }

  // Кнопка «Создать дочернюю тему» в карточке пресетов
  const btnCreateChild = document.getElementById('theme-btn-create-child');
  if (btnCreateChild) {
    btnCreateChild.addEventListener('click', () => {
      openCreateChildModal();
    });
  }

  // Слушатель смены базовой темы в модалке «Собрать свою тему на основе существующей»
  const modalParentSelect = document.getElementById('child-theme-parent-select');
  if (modalParentSelect) {
    modalParentSelect.addEventListener('change', () => {
      const selectedBase = modalParentSelect.value;
      renderBaseThemeSwatches(selectedBase);
      const baseTheme = window.themeEngine?.getTheme(selectedBase);
      const baseName = baseTheme?.name || selectedBase;
      const keepEditsCb = document.getElementById('child-theme-keep-edits');
      if (keepEditsCb) {
        keepEditsCb.checked = (selectedBase === presetSelect?.value);
      }
      const nameInput = document.getElementById('child-theme-name-input');
      if (nameInput && nameInput.dataset.autoFilled === 'true') {
        nameInput.value = `${baseName} (${t('ui.thm.myCopySuffix', 'Моя тема')})`;
      }
      const descInput = document.getElementById('child-theme-desc-input');
      if (descInput && descInput.dataset.autoFilled === 'true') {
        descInput.value = `${t('ui.thm.basedOnPrefix', 'Собрана на основе')}: ${baseName}`;
      }
    });
  }

  const modalNameInput = document.getElementById('child-theme-name-input');
  if (modalNameInput) {
    modalNameInput.addEventListener('input', () => {
      modalNameInput.dataset.autoFilled = 'false';
    });
  }
  const modalDescInput = document.getElementById('child-theme-desc-input');
  if (modalDescInput) {
    modalDescInput.addEventListener('input', () => {
      modalDescInput.dataset.autoFilled = 'false';
    });
  }

  // Кнопка подтверждения создания дочерней темы в модалке
  const btnConfirmCreate = document.getElementById('btn-confirm-create-child');
  if (btnConfirmCreate) {
    btnConfirmCreate.addEventListener('click', () => {
      const nameInput = document.getElementById('child-theme-name-input');
      const parentSelectEl = document.getElementById('child-theme-parent-select');
      const descInput = document.getElementById('child-theme-desc-input');
      const keepEditsCb = document.getElementById('child-theme-keep-edits');

      const name = nameInput?.value.trim();
      const parentId = parentSelectEl?.value || 'theme-dark-slate';
      const desc = descInput?.value.trim() || '';
      const keepEdits = keepEditsCb ? keepEditsCb.checked : true;

      if (!name) {
        showToast('Создание темы', 'Пожалуйста, введите название дочерней темы.', 'warning');
        return;
      }

      if (!window.themeEngine) return;

      try {
        // Если пользователь хочет стартовать с чистой палитры выбранной базовой темы
        if (!keepEdits) {
          loadPreset(parentId);
        }

        const tokens = collectTokensFromUI();
        const state = collectFullStateFromUI();
        state.name = name;

        const createdTheme = window.themeEngine.createChildTheme({
          name,
          parentId,
          tokens,
          settings: state,
          description: desc,
        });

        // Применяем созданную тему
        window.themeEngine.applyTheme(createdTheme.id);

        // Закрываем модальное окно
        const modalEl = document.getElementById('themeCreateChildModal');
        if (modalEl && window.bootstrap) {
          window.bootstrap.Modal.getInstance(modalEl)?.hide();
        }

        const parentTheme = window.themeEngine.getTheme(parentId);
        showToast('Тема оформления', `Тема «${name}» успешно создана на базе «${parentTheme?.name || parentId}»!`, 'success');
      } catch (err) {
        showToast('Ошибка создания', err.message, 'danger');
      }
    });
  }

  // Кнопка Удалить дочернюю тему
  const btnDeleteChild = document.getElementById('theme-btn-delete-child');
  if (btnDeleteChild) {
    btnDeleteChild.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : null;
      if (!selectedPreset || !window.themeEngine?.isChildTheme(selectedPreset)) return;

      const childTheme = window.themeEngine.getChildTheme(selectedPreset);
      const parentTheme = window.themeEngine.getTheme(childTheme?.parentId);

      if (confirm(`Удалить дочернюю тему «${childTheme?.name || selectedPreset}»? Это действие нельзя отменить.`)) {
        window.themeEngine.deleteChildTheme(selectedPreset);
        showToast('Удаление темы', `Дочерняя тема удалена. Активирована базовая тема «${parentTheme?.name || 'Стандартная'}».`, 'info');
      }
    });
  }

  // Кнопка Сбросить к родителю
  const btnResetToParent = document.getElementById('theme-btn-reset-to-parent');
  if (btnResetToParent) {
    btnResetToParent.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : null;
      if (!selectedPreset || !window.themeEngine?.isChildTheme(selectedPreset)) return;

      const childTheme = window.themeEngine.getChildTheme(selectedPreset);
      const parentTheme = window.themeEngine.getTheme(childTheme?.parentId);

      if (confirm(`Сбросить все параметры темы «${childTheme?.name}» к исходным значениям родителя «${parentTheme?.name || 'Стандартная'}»?`)) {
        window.themeEngine.resetChildThemeToParent(selectedPreset);
        loadPreset(selectedPreset, () => {
          if (window.themeEngine) window.themeEngine.previewTheme(selectedPreset);
          if (typeof onUpdate === 'function') onUpdate();
        });
        showToast('Сброс к родителю', `Параметры темы сброшены к базовым значениям «${parentTheme?.name || 'Стандартная'}».`, 'info');
      }
    });
  }

  // Кнопка Переименовать дочернюю тему
  const btnRenameChild = document.getElementById('theme-btn-rename-child');
  if (btnRenameChild) {
    btnRenameChild.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : null;
      if (!selectedPreset || !window.themeEngine?.isChildTheme(selectedPreset)) return;

      const childTheme = window.themeEngine.getChildTheme(selectedPreset);
      const renameInput = document.getElementById('child-theme-rename-input');
      if (renameInput) renameInput.value = childTheme?.name || '';

      const modalEl = document.getElementById('themeRenameChildModal');
      if (modalEl && window.bootstrap) {
        window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
      }
    });
  }

  // Кнопка подтверждения переименования в модалке
  const btnConfirmRename = document.getElementById('btn-confirm-rename-child');
  if (btnConfirmRename) {
    btnConfirmRename.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : null;
      if (!selectedPreset || !window.themeEngine?.isChildTheme(selectedPreset)) return;

      const renameInput = document.getElementById('child-theme-rename-input');
      const newName = renameInput?.value.trim();
      if (!newName) {
        showToast('Переименование', 'Введите новое имя темы.', 'warning');
        return;
      }

      window.themeEngine.updateChildTheme(selectedPreset, { name: newName });

      const modalEl = document.getElementById('themeRenameChildModal');
      if (modalEl && window.bootstrap) {
        window.bootstrap.Modal.getInstance(modalEl)?.hide();
      }

      showToast('Переименование', `Тема переименована в «${newName}».`, 'success');
    });
  }

  // Кнопка Сбросить тему (в тулбаре)
  const btnReset = document.getElementById('theme-btn-reset');
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : 'theme-dark-slate';
      if (confirm('Сбросить несохраненные изменения редактора к исходным значениям текущей темы?')) {
        if (window.themeEngine) {
          window.themeEngine.clearCustomOverrides();
        }
        loadPreset(selectedPreset, () => {
          if (window.themeEngine) {
            window.themeEngine.previewTheme(selectedPreset);
          }
          if (typeof onUpdate === 'function') onUpdate();
        });
        showToast('Сброс настроек', 'Несохраненные настройки формы сброшены к текущей теме.', 'info');
      }
    });
  }

  // Кнопка Экспорт JSON
  const btnExport = document.getElementById('theme-btn-export');
  if (btnExport) {
    btnExport.addEventListener('click', () => {
      const selectedPreset = presetSelect ? presetSelect.value : 'theme-dark-slate';
      const isChild = window.themeEngine?.isChildTheme(selectedPreset);
      const childTheme = isChild ? window.themeEngine.getChildTheme(selectedPreset) : null;
      const state = collectFullStateFromUI();

      if (isChild && childTheme) {
        state.isChild = true;
        state.parentId = childTheme.parentId;
        state.name = childTheme.name;
      }

      const jsonStr = JSON.stringify(state, null, 2);
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ai-theme-${(state.name || 'custom').toLowerCase().replace(/\s+/g, '-')}-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('Экспорт темы', 'Конфигурация темы сохранена в файл JSON.', 'info');
    });
  }

  // Импорт JSON
  const fileImport = document.getElementById('theme-file-import');
  if (fileImport) {
    fileImport.addEventListener('change', (e) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const imported = JSON.parse(event.target?.result);
          applyStateToUI(imported);
          if (typeof onUpdate === 'function') onUpdate();

          // Если в импортированном файле указана дочерняя тема, предлагаем сохранить ее в дочерние
          if (imported.parentId && window.themeEngine) {
            const themeName = imported.name || 'Импортированная тема';
            if (confirm(`Импортирована дочерняя тема «${themeName}» на базе «${imported.parentId}». Зарегистрировать ее как отдельную дочернюю тему?`)) {
              const tokens = collectTokensFromUI();
              const newChild = window.themeEngine.createChildTheme({
                name: themeName,
                parentId: imported.parentId,
                tokens,
                settings: imported,
              });
              window.themeEngine.applyTheme(newChild.id);
            }
          }

          showToast('Импорт темы', `Тема «${imported.name || 'Пользовательская'}» успешно импортирована!`, 'success');
        } catch (err) {
          showToast('Ошибка импорта', `Не удалось распарсить JSON: ${err.message}`, 'danger');
        }
        fileImport.value = '';
      };
      reader.readAsText(file);
    });
  }

  // Кнопка Копировать CSS
  const btnCopyCss = document.getElementById('theme-btn-copy-css');
  if (btnCopyCss) {
    btnCopyCss.addEventListener('click', () => {
      const css = generateCssString();
      const output = document.getElementById('theme-css-output');
      if (output) output.value = css;

      const modalEl = document.getElementById('themeCssModal');
      if (modalEl && window.bootstrap) {
        new window.bootstrap.Modal(modalEl).show();
      } else {
        navigator.clipboard.writeText(css).then(() => {
          showToast('Копирование CSS', 'CSS-код переменных скопирован в буфер обмена!', 'success');
        });
      }
    });
  }

  // Кнопка копирования внутри модального окна
  const btnCopyModal = document.getElementById('btn-copy-css-modal');
  if (btnCopyModal) {
    btnCopyModal.addEventListener('click', () => {
      const output = document.getElementById('theme-css-output');
      if (output) {
        navigator.clipboard.writeText(output.value).then(() => {
          showToast('Буфер обмена', 'CSS-код скопирован!', 'success');
        });
      }
    });
  }
}
