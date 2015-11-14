console.log('Loading function');

test = require('./required-file.js');

exports.lambda_handler = function(event, context) {
    console.log('Received event:', JSON.stringify(event, null, 2));
    context.succeed(event);
};
