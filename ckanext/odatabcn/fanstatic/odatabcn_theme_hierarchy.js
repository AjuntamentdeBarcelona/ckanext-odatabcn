// Enable JavaScript's strict mode. Strict mode catches some common
// programming errors and throws exceptions, prevents some unsafe actions from
// being taken, and disables some confusing and bad JavaScript features.

"use strict";

(function (jQuery) {
	
	/** Show organizations hierarchically **/
	var parentLi = $('#organization').children('.parent');
	parentLi.sort(function(a, b) {
		var compA = $(a).text().toUpperCase();
		var compB = $(b).text().toUpperCase();
		return (compA < compB) ? -1 : (compA > compB) ? 1 : 0;
	});
	
	$.each(parentLi, function(idx, itm) { 
		$('#organization').append(itm); 
		$(this).append("<ul></ul>");
	});

  $('#organization').children("li[parent]").each(function (el) {
	
    var parentId = $(this).attr('parent');
    if (parentId != "") {
      $('#' + parentId + " ul").append($(this));
    }

  });
  
  
  if ($('#tags .tag-list').height() > $('#tags .tag-content').height()) {
    $('#show-more-tags').show();
  }
  
  $('#show-more-tags').click(function () {
    $('#tags .tag-content').toggleClass('tag-content-show-all');
    $('#show-more-tags').toggleClass('shown');
  });
  
  $('.filter-block .module-heading').click(function () {
    $(this).next("nav").slideToggle();
	$(this).children('.pull-right').toggleClass('bcn-icon-menys-bold');
	$(this).children('.pull-right').toggleClass('bcn-icon-mes-bold');
  }); 
  
   $('.nav-item.active').parent().parent("nav").show();
  
  
  /** Affix navigation **/
  $('#nav').affix();
  $('#nav-wrapper').height($("#nav").height());
  
  /** Show modal **/
  $('#dashboardModal').modal('show');
 
  
  function checkSize () {
    var width = Math.max(document.documentElement.clientWidth, window.innerWidth || 0);
    
    if (width < 767) {
      $('.secondary .organization-info').prependTo('.primary');
    } else {
      $('.primary .organization-info').prependTo('.secondary'); 
    }
    
  }
  
  /** Load user comments **/
  $(document).ready(checkSize);
  $(window).resize(checkSize);
  
  var commentsLoaded = false;
  $(window).scroll(function(){
	$(".dataset-comments").each(function () {
		if ($(this).isOnScreen() && !commentsLoaded) {
			commentsLoaded = true;
			$(this).load( "/util/comentariosDataset.php?id=" + $(this).attr('id') + "&lang=" + $(this).attr('lang'), function (response, status, xhr) {
				if ( status == "error" ) {
					$(this).parents("#resource-additional-info").hide();
				} else {
					$(this).css('background', 'none');
					
					var identifier = window.location.hash;
					if (identifier === "#comment-form") {
						var body = $("html, body");
						body.stop().animate({scrollTop:$("#comments").offset().top}, 500, 'swing');
					}
				}
			});
		}
	  });
	});
	
	/** Site menu: do not keep dropdown open on click **/
	$('.masthead .dropdown-toggle').click(function(e) {
		var width = Math.max(document.documentElement.clientWidth, window.innerWidth || 0);
		
		if (width >= 767) {
			e.stopPropagation();
			e.preventDefault();
		}
	});
	
	$.fn.isOnScreen = function(){

		var win = $(window);

		var viewport = {
			top : win.scrollTop(),
			left : win.scrollLeft()
		};
		viewport.right = viewport.left + win.width();
		viewport.bottom = viewport.top + win.height();

		var bounds = this.offset();
		bounds.right = bounds.left + this.outerWidth();
		bounds.bottom = bounds.top + this.outerHeight();

		return (!(viewport.right < bounds.left || viewport.left > bounds.right || viewport.bottom < bounds.top || viewport.top > bounds.bottom));

	};

})(this.jQuery);
