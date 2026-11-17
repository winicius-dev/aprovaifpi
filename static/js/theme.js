/**
 * AprovaIFPI — Theme Controller (Dark Mode Individual por Conta)
 * O tema é individual e persistido no Perfil de cada usuário (banco de dados).
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

  // O tema da conta é determinado pelo atributo data-theme inserido pelo Django no <html>
  var currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
  applyTheme(currentTheme);

  // Expõe função global para alternância imediata (ex: tela de configurações)
  window.setAprovaTheme = function(theme, syncServer) {
    if (theme !== 'dark' && theme !== 'light') return;
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

    // Sincroniza com a conta no servidor via API
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

  // Ao carregar o DOM, sincroniza os seletores da página de configurações
  document.addEventListener('DOMContentLoaded', function() {
    var theme = document.documentElement.getAttribute('data-theme') || 'light';
    applyTheme(theme);

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
      if (theme === 'light') lightCard.classList.add('active');
      else lightCard.classList.remove('active');
      lightCard.addEventListener('click', function() {
        window.setAprovaTheme('light', true);
      });
    }
    if (darkCard) {
      if (theme === 'dark') darkCard.classList.add('active');
      else darkCard.classList.remove('active');
      darkCard.addEventListener('click', function() {
        window.setAprovaTheme('dark', true);
      });
    }
  });
})();
