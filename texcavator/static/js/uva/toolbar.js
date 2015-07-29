// FL-27-Jan-2012 Created
// FL-29-Nov-2013 Changed

dojo.require("dojo.data.ItemFileWriteStore");
dojo.require("dojo.date.locale");
dojo.require("dojo.i18n");
dojo.require("dojo.store.Memory");

dojo.require("dijit.Calendar");
dojo.require("dijit.Dialog");
dojo.require("dijit.Toolbar");
dojo.require("dijit.ToolbarSeparator");
dojo.require("dijit.Tooltip");
dojo.require("dijit.form.Button");
dojo.require("dijit.form.DateTextBox");
dojo.require("dijit.form.CheckBox");
dojo.require("dijit.form.ComboBox");
dojo.require("dijit.form.NumberSpinner");
dojo.require("dijit.form.RadioButton");
dojo.require("dijit.form.SimpleTextarea");
dojo.require("dijit.form.TextBox");
dojo.require("dijit.layout.ContentPane");
dojo.require("dijit.layout.TabContainer");

dojo.require("dojox.widget.Dialog");

/*
var storeDateLimits = function( SRU_DATE_LIMITS )
var toDateString = function( date )
var getDateBeginStr = function()
var getDateEndStr   = function()
var getDateRangeString = function()
var getBeginDate = function()
var getEndDate = function()
var createToolbar = function()
var toolbarSearch = function()
var toolbarQuery = function()
var toolbarAbout = function()
var showAbout = function()
var createAbout = function()
*/

var minDate; // fixed for project
var maxDate; // fixed for project
var beginDateMax; // changeable
var endDateMin; // changeable
var beginDate = minDate;
var endDate = maxDate;


var storeDateLimits = function(SRU_DATE_LIMITS) {
	//	console.log( "storeDateLimits()" );
	//	console.log( "SRU_DATE_LIMITS: " + SRU_DATE_LIMITS );

	var min_date = SRU_DATE_LIMITS[0].toString();
	var max_date = SRU_DATE_LIMITS[1].toString();

	// parseInt with radix 10 to prevent trouble with leading 0's (octal, hex)
	// substring: from index is included, to index is not included
	var min_year = parseInt(min_date.substring(0, 4), 10);
	var max_year = parseInt(max_date.substring(0, 4), 10);

	var min_month = parseInt(min_date.substring(4, 6), 10) - 1; // month 0...11
	var max_month = parseInt(max_date.substring(4, 6), 10) - 1; // month 0...11

	var min_day = parseInt(min_date.substring(6, 8), 10);
	var max_day = parseInt(max_date.substring(6, 8), 10);

	minDate = new Date(min_year, min_month, min_day);
	maxDate = new Date(max_year, max_month, max_day);
	beginDate = minDate;
	endDate = maxDate;

	// update widget contents
	dijit.byId("begindate").set("constraints", {
		min: minDate,
		max: maxDate
	});
	dijit.byId("enddate").set("constraints", {
		min: minDate,
		max: maxDate
	});
	dijit.byId("begindate").set("value", minDate);
	dijit.byId("enddate").set("value", maxDate);

	var min_date = dijit.byId("begindate").get("value");
	var max_date = dijit.byId("enddate").get("value");
}; // storeDateLimits()


// Converts a string (YYYY-MM-DD) into a Date
function stringToDate(strDate) {
	var dateParts = strDate.split("-");
	return new Date(dateParts[0], (dateParts[1] - 1), dateParts[2]);
}


// Converts a Date into YYYYMMDD (from http://stackoverflow.com/a/3067896/3710392)
var toDateString = function(date) {
	var yyyy = date.getFullYear().toString();
	var mm = (date.getMonth() + 1).toString(); // getMonth() is zero-based
	var dd = date.getDate().toString();
	return yyyy + (mm[1] ? mm : "0" + mm[0]) + (dd[1] ? dd : "0" + dd[0]); // padding
}; // toDateString()


var getDate_Begin_Str = function() {
	var bds = toDateString(beginDate);
	return bds.substring(0, 4) + '-' + bds.substring(4, 6) + '-' + bds.substring(6, 8);
};


var getDate_End_Str = function() {
	var eds = toDateString(endDate);
	return eds.substring(0, 4) + '-' + eds.substring(4, 6) + '-' + eds.substring(6, 8);
};


var getDateBeginStr = function() {
	return toDateString(beginDate);
};


var getDateEndStr = function() {
	return toDateString(endDate);
};


var getDateRangeString = function() {
	return getDateBeginStr() + ',' + getDateEndStr();
};


var getBeginDate = function() {
	return beginDate;
};


var getEndDate = function() {
	return endDate;
};


var createToolbar = function() {
	var toolbar = new dijit.Toolbar({
		style: "height: 26px;"
	}, "span-toolbar"); // id="span-toolbar" in base.html

	require(["dojo/date"], function(date) {
		beginDateMax = date.add(maxDate, "day", -1);
		endDateMin = date.add(minDate, "day", 1);
	});

	var btnDateFilterBegin = new dijit.form.Button({
		label: "<img src = '/static/image/icon/Tango/22/apps/office-calendar.png')/>Search period: from",
		showLabel: true,
		disabled: true
	});

	var beginDateTB = new dijit.form.DateTextBox({
		id: "begindate",
		style: "width: 90px;",
		value: minDate,
		constraints: {
			min: minDate,
			max: beginDateMax
		},
		onChange: function() {
			// Set the beginDate variable
			beginDate = beginDateTB.value;

			// set new min constraint for endDate
			require(["dojo/date"], function(date) {
				endDateTB.constraints.min = date.add(beginDateTB.value, "day", 1);
			});

			// Update the slider
			updateYearSlider(beginDateTB.value, endDateTB.value);
		}
	});

	var btnDateFilterEnd = new dijit.form.Button({
		label: "to",
		showLabel: true,
		disabled: true
	});

	var endDateTB = new dijit.form.DateTextBox({
		id: "enddate",
		style: "width: 90px;",
		value: maxDate,
		constraints: {
			min: endDateMin,
			max: maxDate
		},
		onChange: function() {
			// Set the endDate variable
			endDate = endDateTB.value;

			// Set new max constraint for beginDateTB
			require(["dojo/date"], function(date) {
				beginDateTB.constraints.max = date.add(endDateTB.value, "day", -1);
			});

			// Update the slider
			updateYearSlider(beginDateTB.value, endDateTB.value);
		}
	});

	toolbar.addChild(btnDateFilterBegin);
	toolbar.addChild(beginDateTB);
	toolbar.addChild(btnDateFilterEnd);
	toolbar.addChild(endDateTB);
	toolbar.addChild(new dijit.ToolbarSeparator());

	var btnQuery = new dijit.form.Button({
		label: "<img src = '/static/image/icon/Tango/22/apps/utilities-dictionary.png')/>Query",
		showLabel: true,
		onClick: toolbarQuery
	});
	toolbar.addChild(btnQuery);

	var btnCloud = new dijit.form.Button({
		label: "<img src = '/static/image/icon/Tango/22/actions/check-spelling.png')/>Cloud Data",
		showLabel: true,
		onClick: showCloudDlg
	});
	toolbar.addChild(btnCloud);

	// remaining icons style: "float:right"

	var btnAbout = new dijit.form.Button({
		label: "<img src='/static/image/icon/gnome/22/actions/help-about.png'/>About",
		showLabel: true,
		style: "float:right",
		onClick: toolbarAbout
	});
	toolbar.addChild(btnAbout);


	var btnConfig = new dijit.form.Button({
		label: "<img src = '/static/image/icon/Tango/22/categories/utilities.png')/>Config",
		showLabel: true,
		style: "float:right",
		onClick: toolbarConfig // config.js
	});
	toolbar.addChild(btnConfig);


	var btnUser = new dijit.form.Button({
		id: "toolbar-user",
		label: "<img src = '/static/image/icon/Tango/22/apps/preferences-users.png')/>",
		showLabel: true,
		style: "float:right",
		onClick: function() {
			if (dijit.byId("dlg-logout") !== undefined) {
				dijit.byId("dlg-logout").destroyRecursive();
			}
			createLogout();
			showLogout();
		}
	});
	toolbar.addChild(btnUser);
}; // createToolbar()

dojo.addOnLoad(createToolbar);


var toolbarQuery = function() {
	createQueryDlg(); // query.js : this fills the querylistStore
	dijit.byId("dlg-query").show();
};


var toolbarAbout = function() {
	createAbout();
	showAbout();
};


var showAbout = function() {
	dijit.byId("about").show();
};


var createAbout = function() {
	var title = "Texcavator - Collaborating Institutes";
	var style = "width: 420px; height: 420px; text-align: right; line-height: 24px; margin: 5px;";

	var dlgAbout = new dijit.Dialog({
		id: "about",
		title: title
	});

	dojo.style(dlgAbout.closeButtonNode, "visibility", "hidden"); // hide the ordinary close button

	var container = dlgAbout.containerNode;

	var cpdiv = dojo.create("div", {
		id: "cp-div"
	}, container);
	var aboutContainer = new dijit.layout.ContentPane({
		title: "About",
		style: style
	}, "cp-div");

	dojo.create("div", {
		innerHTML: "<a href='http://wahsp.nl' target='_blank'><img src='/static/image/logos/WAHSPlogo.png' height='48' align='left' /></a>",
		style: "clear: both"
	}, aboutContainer.domNode);

	// var innerHTML = "<a href='/static/BiLand_manual.pdf' target='_blank'>BiLand Manual</a>";
	var innerHTML = "<a href='/static/WAHSP_manual.pdf' target='_blank'>WAHSP/BiLand Manual</a>";

	dojo.create("div", {
		innerHTML: innerHTML,
		style: "clear: both"
	}, aboutContainer.domNode);

	var client_timestamp = getClientTimestamp(); // timestamp.js
	var server_timestamp = getServerTimestamp(); // timestamp.js

	dojo.create("div", {
		innerHTML: "Client timestamp: " + client_timestamp,
		style: "clear: both"
	}, aboutContainer.domNode);
	dojo.create("div", {
		innerHTML: "Server timestamp: " + server_timestamp,
		style: "clear: both"
	}, aboutContainer.domNode);
	dojo.create("div", {
		innerHTML: "<hr>",
		style: "clear: both"
	}, aboutContainer.domNode);

	dojo.create("div", {
		innerHTML: "<a href='http://www.uva.nl' target='_blank'><img src='/static/image/logos/UvA.gif' height='50' align='left' /></a>",
		style: "clear: both"
	}, aboutContainer.domNode);
	dojo.create("div", {
		innerHTML: "<hr>",
		style: "clear: both"
	}, aboutContainer.domNode);

	dojo.create("div", {
		innerHTML: "<a href='http://www.uu.nl' target='_blank'><img src='/static/image/logos/UniversiteitUtrecht.gif' height='50' align='left' /></a>",
		style: "clear: both"
	}, aboutContainer.domNode);
	dojo.create("div", {
		innerHTML: "<hr>",
		style: "clear: both"
	}, aboutContainer.domNode);

	dojo.create("div", {
		innerHTML: "<a href='http://www.kb.nl' target='_blank'><img src='/static/image/logos/KB.gif' height='40' align='left' /></a>",
		style: "clear: both"
	}, aboutContainer.domNode);
	dojo.create("div", {
		innerHTML: "<hr>",
		style: "clear: both"
	}, aboutContainer.domNode);

	dojo.create("div", {
		innerHTML: "<a href='http://huygensinstituut.knaw.nl' target='_blank'><img src='/static/image/logos/HuygensInstituut.gif' height='30' align='left' /></a>",
		style: "clear: both"
	}, aboutContainer.domNode);

	dojo.create("div", {
		innerHTML: "<hr>",
		style: "clear: both"
	}, aboutContainer.domNode);
	dojo.create("div", {
		innerHTML: "<a href='http://staatsbibliothek-berlin.de/' target='_blank'><img src='/static/image/logos/StaatsbibliothekBerlin.png' height='40' align='left' /></a>",
		style: "clear: both"
	}, aboutContainer.domNode);

	var actionBar = dojo.create("div", {
		className: "dijitDialogPaneActionBar",
		style: "height: 30px"
	}, container);

	var bClose = new dijit.form.Button({
		label: "<img src='/static/image/icon/Tango/16/actions/dialog-close.png'/> Close",
		showLabel: true,
		role: "presentation",
		onClick: function() {
			dijit.byId("about").destroyRecursive();
		}
	});
	actionBar.appendChild(bClose.domNode);
}; // createAbout

// [eof]