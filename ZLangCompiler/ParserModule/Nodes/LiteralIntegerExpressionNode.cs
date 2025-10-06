using LexerModule;

namespace ParserModule.Nodes;

public sealed class LiteralIntegerExpressionNode : PrimaryExpressionNode
{
    private readonly Token _token;

    public LiteralIntegerExpressionNode(Token token)
    {
        _token = token;
        Value = int.Parse(token.Lexeme);
    }

    public int Value { get; }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitIntegerNumberExpression(this);
    }
}