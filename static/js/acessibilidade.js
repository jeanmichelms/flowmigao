// acessibilidade.js
// Funções compartilhadas de acessibilidade: anúncios para leitores de tela e modais acessíveis.

(function () {
    const SELETOR_FOCAVEL = [
        'a[href]',
        'button:not([disabled])',
        'input:not([disabled]):not([type="hidden"])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])',
    ].join(', ');

    // Lê a mensagem para quem usa leitor de tela, sem tirar o foco do lugar
    function anunciar(mensagem) {
        const regiao = document.getElementById('anuncios');
        if (!regiao) {
            return;
        }
        regiao.textContent = '';
        // Pequeno atraso para o leitor de tela perceber a troca, mesmo com mensagem repetida
        setTimeout(function () {
            regiao.textContent = mensagem;
        }, 100);
    }

    // Liga/desliga uma referência no aria-describedby sem apagar as que já existem
    function descreverCom(campo, id, ativo) {
        const ids = (campo.getAttribute('aria-describedby') || '').split(' ').filter(Boolean);
        const restantes = ids.filter(function (item) { return item !== id; });
        if (ativo) {
            restantes.push(id);
        }
        if (restantes.length) {
            campo.setAttribute('aria-describedby', restantes.join(' '));
        } else {
            campo.removeAttribute('aria-describedby');
        }
    }

    // Transforma o overlay em um diálogo modal acessível:
    // - foco vai para dentro ao abrir e volta para quem abriu ao fechar
    // - Tab/Shift+Tab ficam presos dentro do modal
    // - Esc ou clique fora fecham
    // - o restante da página fica inerte (fora do alcance do teclado e do leitor de tela)
    function criarModal(modal, opcoes) {
        opcoes = opcoes || {};
        let origemFoco = null;

        // O modal fica direto no <body> para podermos deixar o resto da página inerte
        document.body.appendChild(modal);

        function restoDaPagina() {
            return Array.from(document.body.children).filter(function (el) {
                return el !== modal && el.id !== 'anuncios' && el.tagName !== 'SCRIPT';
            });
        }

        function estaAberto() {
            return !modal.hidden;
        }

        function abrir() {
            origemFoco = document.activeElement;
            restoDaPagina().forEach(function (el) { el.inert = true; });
            modal.hidden = false;
            modal.classList.add('is-open');
            document.body.style.overflow = 'hidden';

            const alvo = opcoes.focoInicial || modal.querySelector(SELETOR_FOCAVEL);
            if (alvo) {
                alvo.focus();
            }
            if (opcoes.aoAbrir) {
                opcoes.aoAbrir();
            }
        }

        function fechar() {
            modal.classList.remove('is-open');
            modal.hidden = true;
            restoDaPagina().forEach(function (el) { el.inert = false; });
            document.body.style.overflow = '';

            if (origemFoco && document.contains(origemFoco)) {
                origemFoco.focus();
            }
        }

        modal.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                event.preventDefault();
                fechar();
                return;
            }
            if (event.key !== 'Tab') {
                return;
            }

            const focaveis = Array.from(modal.querySelectorAll(SELETOR_FOCAVEL));
            if (!focaveis.length) {
                return;
            }
            const primeiro = focaveis[0];
            const ultimo = focaveis[focaveis.length - 1];

            if (event.shiftKey && document.activeElement === primeiro) {
                event.preventDefault();
                ultimo.focus();
            } else if (!event.shiftKey && document.activeElement === ultimo) {
                event.preventDefault();
                primeiro.focus();
            }
        });

        modal.addEventListener('click', function (event) {
            if (event.target === modal) {
                fechar();
            }
        });

        return { abrir: abrir, fechar: fechar, estaAberto: estaAberto };
    }

    // Se o formulário voltou com erros, leva o foco ao resumo para que ele seja lido primeiro
    document.addEventListener('DOMContentLoaded', function () {
        const resumoErros = document.getElementById('resumo-erros');
        if (resumoErros) {
            resumoErros.focus();
        }
    });

    window.FlowMigao = {
        anunciar: anunciar,
        descreverCom: descreverCom,
        criarModal: criarModal,
    };
})();
