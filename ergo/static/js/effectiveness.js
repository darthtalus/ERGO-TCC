$(".btn-effect").on("click", (a) => {
  console.log("a");
  const valor = a.target.getAttribute("data-value");
  $("#id_effectiveness").val(valor);
  $("#id_effectiveness_form").trigger("submit");
});
