// viacep.js

document.addEventListener('DOMContentLoaded', function() {
    // Pegando os elementos do formulário (verifique se os IDs batem com o seu HTML)
    const cepInput = document.getElementById('id_cep');
    const enderecoInput = document.getElementById('id_endereco');
    const bairroInput = document.getElementById('id_bairro');
    const cidadeInput = document.getElementById('id_cidade');
    const estadoInput = document.getElementById('id_estado');
    const numeroInput = document.getElementById('id_numero');

    // Função que busca o CEP
    cepInput.addEventListener('blur', function() {
        // Remove tudo que não for número do CEP
        let cep = cepInput.value.replace(/\D/g, '');

        if (cep !== "") {
            // Expressão regular para validar o CEP
            let validacep = /^[0-9]{8}$/;

            if(validacep.test(cep)) {
                // Exibe "..." enquanto carrega
                enderecoInput.value = "...";
                bairroInput.value = "...";
                cidadeInput.value = "...";
                estadoInput.value = "...";

                // Chamada à API
                fetch(`https://viacep.com.br/ws/${cep}/json/`)
                    .then(response => response.json())
                    .then(data => {
                        if (!("erro" in data)) {
                            // Atualiza os campos com os dados da API
                            enderecoInput.value = data.logradouro;
                            bairroInput.value = data.bairro;
                            cidadeInput.value = data.localidade;
                            estadoInput.value = data.uf;
                            
                            // Coloca o cursor no campo de número para o usuário continuar
                            numeroInput.focus();
                        } else {
                            alert("CEP não encontrado.");
                            limparCampos();
                        }
                    })
                    .catch(error => {
                        console.error('Erro ao buscar o CEP:', error);
                        alert("Erro ao buscar o CEP.");
                    });
            } else {
                alert("Formato de CEP inválido.");
            }
        }
    });

    function limparCampos() {
        enderecoInput.value = "";
        bairroInput.value = "";
        cidadeInput.value = "";
        estadoInput.value = "";
    }
});