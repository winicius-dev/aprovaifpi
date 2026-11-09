/**
 * AprovaIFPI — Theme Controller (Dark Mode)
 * Gerencia a persistência em localStorage e sincronização com o backend.
 */
(function() {
  function applyTheme(theme) {
    if (theme === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
      document.documentElement.classList.add('dark-mode');
      if (document.body) document.body.classList.add('dark-mode');
    } else {
      document.documentElement.setAttribute('data-theme', 'light');
      document.documentElement.classList.remove('dark-mode');
      if (document.body) document.body.classList.remove('dark-mode');
    }
  }

  // Aplicação instantânea imediata
  var current = localStorage.getItem('aprovaifpi_theme') || 'light';
  applyTheme(current);

  // Expõe função global para alternância
  window.setAprovaTheme = function(theme, syncServer) {
    if (theme !== 'dark' && theme !== 'light') return;
    localStorage.setItem('aprovaifpi_theme', theme);
    applyTheme(theme);

    // Atualiza controles na tela caso existam (ex: na página de configurações)
    var lightCard = document.getElementById('theme-card-light');
    var darkCard = document.getElementById('theme-card-dark');
    var themeSwitch = document.getElementById('switch-tema-escuro');
    var labelStatus = document.getElementById('label-tema-status');

    if (lightCard && darkCard) {
      if (theme === 'dark') {
        lightCard.classList.remove('active');
        darkCard.classList.add('active');
      } else {
        lightCard.classList.add('active');
        darkCard.classList.remove('active');
      }
    }
    if (themeSwitch) {
      themeSwitch.checked = (theme === 'dark');
    }
    if (labelStatus) {
      labelStatus.textContent = (theme === 'dark') ? 'Tema Escuro Ativo' : 'Tema Claro Ativo';
    }

    // Se solicitado sincronizar com servidor via API
    if (syncServer !== false) {
      var csrfToken = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
      fetch('/auth/api/tema/alternar/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ tema_escuro: (theme === 'dark') })
      }).catch(function(err) {
        console.warn('Não foi possível sincronizar tema com o servidor:', err);
      });
    }
  };

  // Garante que assim que o DOM carregar a classe esteja no body e listeners ativos
  document.addEventListener('DOMContentLoaded', function() {
    var theme = localStorage.getItem('aprovaifpi_theme') || 'light';
    applyTheme(theme);

    // Inicializa controles de UI se estiver na tela de configurações
    var themeSwitch = document.getElementById('switch-tema-escuro');
    var lightCard = document.getElementById('theme-card-light');
    var darkCard = document.getElementById('theme-card-dark');
    var labelStatus = document.getElementById('label-tema-status');

    if (themeSwitch) {
      themeSwitch.checked = (theme === 'dark');
      themeSwitch.addEventListener('change', function() {
        window.setAprovaTheme(this.checked ? 'dark' : 'light', true);
      });
    }

    if (labelStatus) {
      labelStatus.textContent = (theme === 'dark') ? 'Tema Escuro Ativo' : 'Tema Claro Ativo';
    }

    if (lightCard) {
      lightCard.addEventListener('click', function() {
        window.setAprovaTheme('light', true);
      });
    }
    if (darkCard) {
      darkCard.addEventListener('click', function() {
        window.setAprovaTheme('dark', true);
      });
    }
  });
})();
