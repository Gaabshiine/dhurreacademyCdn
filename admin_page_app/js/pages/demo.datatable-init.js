$(document).ready(function(){
    "use strict";
    $("#basic-datatable").DataTable({
        keys: true,
        language: {
            paginate: {
                previous: "<i class='mdi mdi-chevron-left'>",
                next: "<i class='mdi mdi-chevron-right'>"
            }
        },
        order: [[0, 'desc']], // Order by the first column (ID) in descending order
        drawCallback: function(){
            $(".dataTables_paginate > .pagination").addClass("pagination-rounded");
        }
    });
});
